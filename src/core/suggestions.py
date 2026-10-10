"""
Sugerencias del analizador. Deterministas: se calcula qué le falta de verdad al equipo (roles, huecos defensivos,
cobertura, mecánicas sin usar, infracciones) y qué candidatos LEGALES y de uso real lo resuelven. Los motivos se
construyen con hechos comprobados, así que no pueden inventar efectos ni proponer algo fuera de las reglas del formato.
"""
import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.era_rules import legal_abilities
from src.core.team_validator import RuleViolation, _move_ok, _rules, full_learnset, validate_team
from src.core.types import compute_defensive_matchups
from src.services.smogon import normalize_id as nid

_L = {"es": 0, "en": 1, "fr": 2}
TYPE_NAMES = {
    "Normal": ("Normal", "Normal", "Normal"), "Fire": ("Fuego", "Fire", "Feu"), "Water": ("Agua", "Water", "Eau"),
    "Electric": ("Eléctrico", "Electric", "Électrik"), "Grass": ("Planta", "Grass", "Plante"), "Ice": ("Hielo", "Ice", "Glace"),
    "Fighting": ("Lucha", "Fighting", "Combat"), "Poison": ("Veneno", "Poison", "Poison"), "Ground": ("Tierra", "Ground", "Sol"),
    "Flying": ("Volador", "Flying", "Vol"), "Psychic": ("Psíquico", "Psychic", "Psy"), "Bug": ("Bicho", "Bug", "Insecte"),
    "Rock": ("Roca", "Rock", "Roche"), "Ghost": ("Fantasma", "Ghost", "Spectre"), "Dragon": ("Dragón", "Dragon", "Dragon"),
    "Dark": ("Siniestro", "Dark", "Ténèbres"), "Steel": ("Acero", "Steel", "Acier"), "Fairy": ("Hada", "Fairy", "Fée"),
}
ROLES = {  # id: (movimientos, habilidades, etiqueta es/en/fr)
    "speed": ({"tailwind", "trickroom", "icywind", "electroweb", "thunderwave", "glare"}, set(),
              ("control de velocidad", "speed control", "contrôle de vitesse")),
    "fakeout": ({"fakeout"}, set(), ("Fake Out", "Fake Out", "Fake Out")),
    "redirect": ({"followme", "ragepowder"}, set(), ("redirección (Follow Me / Rage Powder)", "redirection (Follow Me / Rage Powder)", "redirection (Follow Me / Rage Powder)")),
    "intimidate": (set(), {"intimidate"}, ("Intimidación", "Intimidate", "Intimidation")),
    "hazards": ({"stealthrock", "spikes", "toxicspikes", "stickyweb"}, set(), ("trampas (hazards)", "entry hazards", "pièges (hazards)")),
    "removal": ({"rapidspin", "defog", "courtchange", "mortalspin", "tidyup"}, set(), ("remoción de trampas", "hazard removal", "retrait des pièges")),
    "pivot": ({"uturn", "voltswitch", "partingshot", "flipturn", "chillyreception", "teleport"}, set(), ("pivoteo", "pivoting", "pivot")),
    "recovery": ({"recover", "roost", "softboiled", "slackoff", "synthesis", "moonlight", "morningsun", "wish", "milkdrink", "shoreup", "strengthsap"}, set(),
                 ("recuperación de PS", "HP recovery", "récupération de PV")),
}
WANTED = {True: ["speed", "fakeout", "intimidate", "redirect"], False: ["hazards", "removal", "pivot", "recovery"]}  # doubles / singles

# Funciones clave que protegen a un miembro de ser sustituido (aunque no sean "roles" a cubrir)
_SETTERS = {"drought", "drizzle", "sandstream", "snowwarning", "orichalcumpulse", "hadronengine", "grassysurge", "electricsurge", "psychicsurge", "mistysurge"}
_ABUSERS = {"chlorophyll", "swiftswim", "sandrush", "slushrush", "surgesurfer", "solarpower", "protosynthesis", "quarkdrive"}
_KEY_ABS = {"armortail", "queenlymajesty", "dazzling"}                        # bloqueo de prioridad
_KEY_MOVES = {"helpinghand", "wideguard", "quickguard", "lightscreen", "reflect", "auroraveil", "trickroom", "tailwind", "fakeout"}

_T = {  # plantillas (es, en, fr)
    "mega": ("{f} permite Megaevolución y tu equipo no usa ninguna. {s} tiene a {m}: pasa de {b0} a {b1} de estadísticas base totales.",
             "{f} allows Mega Evolution and your team uses none. {s} has {m}: base stat total goes from {b0} to {b1}.",
             "{f} autorise la Méga-Évolution et ton équipe n'en utilise aucune. {s} a {m} : le total de stats de base passe de {b0} à {b1}."),
    "tera": ("{n} de tus Pokémon son débiles al tipo {t}. Teratipo {tt} en {s} le da resistencia a {t}.",
             "{n} of your Pokémon are weak to {t}. Tera {tt} on {s} makes it resist {t}.",
             "{n} de tes Pokémon sont faibles au type {t}. Téra {tt} sur {s} lui donne une résistance à {t}."),
    "z": ("{f} permite Cristales Z y ninguno de tus Pokémon lleva uno. {s} es de tipo {t} y ya tiene {mv}: con {z} lo convierte en su movimiento Z.",
          "{f} allows Z-Crystals and none of your Pokémon holds one. {s} is {t}-type and already has {mv}: {z} turns it into its Z-Move.",
          "{f} autorise les Cristaux Z et aucun de tes Pokémon n'en porte. {s} est de type {t} et a déjà {mv} : {z} en fait sa capacité Z."),
    "role_move": ("Tu equipo no tiene {r}. {s} puede aprender {mv}: sustituye {old}, el movimiento que menos aporta, por {mv}.",
                  "Your team has no {r}. {s} can learn {mv}: replace {old}, its least useful move, with {mv}.",
                  "Ton équipe n'a pas de {r}. {s} peut apprendre {mv} : remplace {old}, son attaque la moins utile, par {mv}."),
    "role_swap": ("Tu equipo no tiene {r}. {c} lo aporta con {mv} ({u}). Sustituye a {s}, el miembro cuya salida quita menos funciones clave.",
                  "Your team has no {r}. {c} provides it with {mv} ({u}). It replaces {s}, the member whose removal costs the fewest key roles.",
                  "Ton équipe n'a pas de {r}. {c} l'apporte avec {mv} ({u}). Il remplace {s}, le membre dont le départ coûte le moins de rôles clés."),
    "hole": ("{names} son débiles al tipo {t} y solo {k} miembro(s) lo resisten. {c} resiste {t} ({u}) y sustituye a {s}, que es débil a ese tipo.",
             "{names} are weak to {t} and only {k} member(s) resist it. {c} resists {t} ({u}) and replaces {s}, which is weak to it.",
             "{names} sont faibles au type {t} et seulement {k} membre(s) le résistent. {c} résiste à {t} ({u}) et remplace {s}, qui y est faible."),
    "cover": ("Ningún movimiento de tu equipo golpea súper efectivo a: {types}. {mv} en {s} cubre {cov}.",
              "No move on your team hits these types super effectively: {types}. {mv} on {s} covers {cov}.",
              "Aucune attaque de ton équipe ne touche super efficacement : {types}. {mv} sur {s} couvre {cov}."),
    "protect": ("{s} no lleva Protect. En dobles casi todos lo llevan: bloquea un turno de daño rival y hace perder tiempo a su control de campo. Sustituye {old}, su movimiento que menos aporta, por Protect.",
                "{s} has no Protect. In doubles nearly everything runs it: it blocks a turn of damage and burns the opponent's field control. Replace {old}, its least useful move, with Protect.",
                "{s} n'a pas Protect. En double presque tous l'ont : il bloque un tour de dégâts et fait perdre du temps au contrôle adverse. Remplace {old}, son attaque la moins utile, par Protect."),
    "tip_mega": ("En {f} solo un Pokémon puede Megaevolucionar por combate. Tu equipo lleva a {m}: planifica en qué turno activarla, porque no podrás hacerlo con otro.",
                 "In {f} only one Pokémon can Mega Evolve per battle. Your team carries {m}: plan which turn to activate it, because you can't do it with another one.",
                 "En {f} un seul Pokémon peut Méga-Évoluer par combat. Ton équipe porte {m} : planifie à quel tour l'activer, car tu ne pourras pas le faire avec un autre."),
    "tip_tera": ("Solo un Pokémon por combate puede Teracristalizarse. Teratipos definidos en tu equipo: {l}.",
                 "Only one Pokémon per battle can Terastallize. Tera types set on your team: {l}.",
                 "Un seul Pokémon par combat peut se Téracristalliser. Types Téra définis dans ton équipe : {l}."),
    "tip_tera_none": ("Solo un Pokémon por combate puede Teracristalizarse y ninguno de los tuyos tiene Teratipo definido: elegirlo según el rival suele marcar la diferencia.",
                      "Only one Pokémon per battle can Terastallize and none of yours has a Tera type set: choosing it according to the opponent often makes the difference.",
                      "Un seul Pokémon par combat peut se Téracristalliser et aucun des tiens n'a de type Téra défini : le choisir selon l'adversaire fait souvent la différence."),
    "tip_z": ("Solo un Movimiento Z por combate. Cristales Z en tu equipo: {l}.", "Only one Z-Move per battle. Z-Crystals on your team: {l}.", "Une seule Capacité Z par combat. Cristaux Z dans ton équipe : {l}."),
    "tip_dyna": ("Dynamax dura 3 turnos y solo un Pokémon por combate puede usarlo. Por estadísticas base, tu mejor candidato es {s}.",
                 "Dynamax lasts 3 turns and only one Pokémon per battle can use it. By base stats, your best candidate is {s}.",
                 "Le Dynamax dure 3 tours et un seul Pokémon par combat peut l'utiliser. Par stats de base, ton meilleur candidat est {s}."),
    "tip_weather": ("Tu estrategia gira en torno a {st} ({w}) y se apoya en ese efecto a través de {ab}. Si {st} cae, pierdes esa ventaja; considera un segundo creador de {w} o un plan alternativo.",
                    "Your strategy revolves around {st} ({w}) and relies on that effect through {ab}. If {st} goes down you lose that edge; consider a second {w} setter or a backup plan.",
                    "Ta stratégie tourne autour de {st} ({w}) et s'appuie sur cet effet via {ab}. Si {st} tombe, tu perds cet avantage ; envisage un second créateur de {w} ou un plan de secours."),
    "tip_weak": ("Tus mayores debilidades de tipo: {l}. Ten preparada una respuesta para esos tipos antes de elegir tus leads.",
                 "Your biggest type weaknesses: {l}. Have an answer ready for those types before picking your leads.",
                 "Tes plus grandes faiblesses de type : {l}. Prépare une réponse à ces types avant de choisir tes leads."),
    "tip_speed": ("Orden de velocidad (nivel 50): {o}. {sc}", "Speed order (level 50): {o}. {sc}", "Ordre de vitesse (niveau 50) : {o}. {sc}"),
    "sc_yes": ("Control de velocidad: {r}.", "Speed control: {r}.", "Contrôle de vitesse : {r}."),
    "sc_no": ("Tu equipo no tiene control de velocidad directo.", "Your team has no direct speed control.", "Ton équipe n'a pas de contrôle de vitesse direct."),
    "tip_rules": ("Reglas clave de {f}: {r}.", "Key rules of {f}: {r}.", "Règles clés de {f} : {r}."),
    "r_pick": ("llevas 6 y eliges {n} en cada combate", "you bring 6 and pick {n} each battle", "tu apportes 6 et en choisis {n} à chaque combat"),
    "r_item": ("no se pueden repetir objetos", "no duplicate items", "pas d'objets en double"),
    "r_ohko": ("prohibidos los movimientos OHKO (Fissure, Sheer Cold...)", "OHKO moves are banned (Fissure, Sheer Cold...)", "attaques K.O. en un coup interdites (Fissure, Zéro Absolu...)"),
    "r_eva": ("prohibidos los efectos de evasión (Double Team, Minimize, Sand Veil, Snow Cloak, Bright Powder...)", "evasion effects are banned (Double Team, Minimize, Sand Veil, Snow Cloak, Bright Powder...)", "effets d'esquive interdits (Double Team, Minimize, Voile Sable, Rideau Neige, Poudre Claire...)"),
    "r_sleep": ("solo un movimiento de sueño por equipo", "only one sleep move per team", "une seule attaque de sommeil par équipe"),
    "r_restr": ("máximo {n} Pokémon restringido(s)", "at most {n} restricted Pokémon", "au maximum {n} Pokémon restreint(s)"),
    "tip_off": ("Tu equipo ataca sobre todo por vía {a} ({n} Pokémon) y casi nada por vía {b}: un rival con mucha defensa {a2} podría frenarte.",
                "Your team attacks mostly through the {a} side ({n} Pokémon) and almost nothing through the {b} side: an opponent with high {a} defense could stall you.",
                "Ton équipe attaque surtout du côté {a} ({n} Pokémon) et presque pas du côté {b} : un adversaire très résistant côté {a} pourrait te ralentir."),
    "phys": ("física", "physical", "physique"), "spec": ("especial", "special", "spéciale"),
    "usage": ("n.º {r} en uso", "#{r} in usage", "n° {r} en usage"),
    "legal": ("legal en {f}", "legal in {f}", "légal en {f}"),
}


KEEP_STATUS = {"fakeout", "tailwind", "trickroom", "followme", "ragepowder", "helpinghand", "wideguard", "quickguard", "lightscreen", "reflect", "auroraveil", "icywind", "electroweb", "willowisp", "thunderwave", "spore", "partingshot", "snarl"}


def _t(key: str, lang: str, **kw: Any) -> str:
    return _T[key][_L.get(lang, 0)].format(**kw)


def _tn(name: str, lang: str) -> str:
    return TYPE_NAMES.get(name, (name,) * 3)[_L.get(lang, 0)]


def _bp(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _meta_rank(pool: Dict[str, Any], live: Dict[str, Any], doubles: bool) -> List[Tuple[Dict[str, Any], Optional[int]]]:
    """Orden de relevancia: uso real si existe; si no, tier del formato (nunca bonos de generación de equipos)."""
    singles = {"uber": 9, "ag": 9, "(uber)": 8, "ou": 8, "(ou)": 7, "uubl": 7, "uu": 6, "rubl": 6, "ru": 5, "nubl": 5, "nu": 4, "(nu)": 4, "publ": 4, "pu": 3, "(pu)": 3, "zubl": 3}
    dbl = {"duber": 9, "dou": 8, "(dou)": 7, "dbl": 7, "duu": 6, "(duu)": 5}
    usage_order = {k: i + 1 for i, (k, _) in enumerate(sorted(live.items(), key=lambda kv: kv[1].get("usage", 0), reverse=True))}

    def score(p: Dict[str, Any]) -> float:
        rank = usage_order.get(nid(p["name"])) or usage_order.get(nid(p.get("baseSpecies") or ""))
        if rank:
            return 100000 - rank
        tier = str(p.get("doublesTier" if doubles else "tier") or "").lower()
        base = (dbl if doubles else singles).get(tier, 0)
        return base * 100 + sum((p.get("baseStats") or {}).values()) / 10

    ranked = sorted((p for p in pool["legal_pokemon"].values() if not p.get("is_mega")), key=score, reverse=True)
    out = []
    for p in ranked:
        r = usage_order.get(nid(p["name"])) or usage_order.get(nid(p.get("baseSpecies") or ""))
        out.append((p, r))
    return out


def _roles_of(slot: Dict[str, Any]) -> Set[str]:
    mv = {nid(m) for m in slot.get("moves", [])}
    ab = nid(slot.get("ability") or "")
    return {r for r, (ms, abs_, _) in ROLES.items() if (ms & mv) or ab in abs_}


def _keys(slot: Dict[str, Any]) -> Set[str]:
    ab, mv = nid(slot.get("ability") or ""), {nid(m) for m in slot.get("moves", [])}
    keys = _roles_of(slot) | {"k:" + m for m in mv & _KEY_MOVES}
    if ab in _SETTERS:
        keys.add("k:setter")
    if ab in _ABUSERS:
        keys.add("k:abuser")
    if ab in _KEY_ABS:
        keys.add("k:prioblock")
    return keys


def make_suggestions(
    slots: List[Dict[str, Any]], pool: Dict[str, Any], live: Dict[str, Any], matrix: Dict[str, Any],
    lang: str, resolve: Any, chart: Dict[str, Dict[str, float]], max_megas: int,
) -> List[Dict[str, Any]]:
    if not slots:
        return []
    mech, fmt = pool["mechanics"], pool["format"]["name"]
    gen = int(mech.get("gen", 9) or 9)
    doubles = pool["format"].get("game_type") == "doubles"
    legal, legal_items, lm = pool["legal_pokemon"], pool["legal_items"], pool["legal_moves"]
    R = _rules(pool)
    ents = {nid(s["species"]): (resolve(s["species"]) or {}) for s in slots}
    ent = lambda s: ents[nid(s["species"])]
    bst = lambda e: sum((e.get("baseStats") or {}).values())
    team_bases = {nid(ent(s).get("baseSpecies") or s["species"]) for s in slots}
    megas_now = sum(1 for s in slots if ent(s).get("is_mega"))
    restricted_now = sum(1 for s in slots if ent(s).get("is_restricted"))
    ranked = _meta_rank(pool, live, doubles)
    out: List[Dict[str, Any]] = []
    touched: Set[str] = set()

    def add(kind: str, tag: str, tgt: Optional[Dict[str, Any]], new: Optional[str], changes: Dict[str, Any], reason: str) -> None:
        out.append({"type": kind, "tag": tag, "target": tgt["species"] if tgt else None, "add": new, "changes": changes, "reason": reason})
        if tgt:
            touched.add(nid(tgt["species"]))

    def usage_txt(rank: Optional[int]) -> str:
        return _t("usage", lang, r=rank) if rank else _t("legal", lang, f=fmt)

    def slot_keys() -> Dict[str, Set[str]]:
        return {s["species"]: _keys(s) for s in slots}

    def unique_role_owner(sp: str) -> bool:
        keys = slot_keys()
        others = set().union(*[k for n, k in keys.items() if n != sp]) if len(slots) > 1 else set()
        me = next(s for s in slots if s["species"] == sp)
        return bool(keys[sp] - others) or ent(me).get("is_mega", False)

    def weak_counts(members: List[Tuple[List[str], str]]) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for types_, ab in members:
            m = compute_defensive_matchups(types_, ab)
            for t in m["x4"] + m["x2"]:
                c[t] = c.get(t, 0) + 1
        return c

    def keeps_defense(tgt: Dict[str, Any], cand: Dict[str, Any]) -> bool:
        """Un reemplazo no puede crear un hueco defensivo nuevo (>=3 débiles a un tipo) ni agravar uno existente."""
        cur = [(list(ent(x).get("types", [])), x.get("ability") or "") for x in slots]
        after = [m for x, m in zip(slots, cur) if x is not tgt] + [(list(cand.get("types", [])), (legal_abilities(cand, gen) or [""])[0])]
        b, a = weak_counts(cur), weak_counts(after)
        return all(not (n >= 3 and n > b.get(t, 0)) for t, n in a.items())

    def swap_ok(tgt: Dict[str, Any], cand: Dict[str, Any]) -> bool:
        if not keeps_defense(tgt, cand):
            return False
        old = ent(tgt)
        if nid(cand.get("baseSpecies") or cand["name"]) in (team_bases - {nid(old.get("baseSpecies") or tgt["species"])}):
            return False
        rmax = mech.get("max_restricted", 0)
        return not (rmax and restricted_now - bool(old.get("is_restricted")) + bool(cand.get("is_restricted")) > rmax)

    def weakest(exclude: Set[str]) -> Optional[Dict[str, Any]]:
        pool_ = [s for s in slots if nid(s["species"]) not in exclude and not unique_role_owner(s["species"])]
        return min(pool_, key=lambda s: (len(_roles_of(s)), bst(ent(s)))) if pool_ else None

    # 1) Infracciones: corrección legal con el mismo validador que usa el creador
    try:
        fixed, notes = validate_team(copy.deepcopy(slots), pool, resolve, max_megas, lang)
        for a, b in zip(slots, fixed):
            ch = {}
            if nid(a.get("item") or "") != nid(b.get("item") or ""):
                ch["item"] = b.get("item")
            if (a.get("ability") or "") != (b.get("ability") or ""):
                ch["ability"] = b.get("ability")
            if [nid(m) for m in a["moves"]] != [nid(m) for m in b["moves"]]:
                ch["moves"] = b["moves"]
            if ch:
                reason = " ".join(n for n in notes if n.split(":")[0].strip() == a["species"])
                add("fix", "fix", a, None, ch, reason)
    except RuleViolation:
        pass  # especies/límites: ya figuran como infracciones en la revisión de reglas
    out = out[:3]

    # 2) Mecánicas exclusivas sin usar
    has_mega = megas_now > 0
    if mech.get("allow_megas") and not has_mega and megas_now < max_megas:
        best = None
        for s in slots:
            e = ent(s)
            for m in legal.values():
                if m.get("is_mega") and not m.get("is_restricted") and nid(m.get("baseSpecies")) == nid(e.get("baseSpecies") or e["name"]):
                    stone = next((v["name"] for v in legal_items.values() if v.get("megaStone") and nid(v["megaStone"]) == nid(m["name"])), None)
                    if stone and (best is None or bst(m) - bst(e) > best[3]):
                        best = (s, m, stone, bst(m) - bst(e))
        if best:
            s, m, stone, _ = best
            add("mega", "mechanic", s, m["name"], {"item": stone}, _t("mega", lang, f=fmt, s=s["species"], m=m["name"], b0=bst(ent(s)), b1=bst(m)))
    if gen == 7 and mech.get("allow_z_moves") and not any((legal_items.get(nid(s.get("item") or ""), {})).get("isZ") for s in slots):
        zc = {v.get("zMoveType"): v["name"] for v in legal_items.values() if v.get("isZ") and v.get("zMoveType")}
        for s in slots:
            for mv in s["moves"]:
                d = lm.get(nid(mv), {})
                if d.get("category") != "Status" and d.get("type") in zc and nid(s["species"]) not in touched:
                    add("set", "mechanic", s, None, {"item": zc[d["type"]]},
                        _t("z", lang, f=fmt, s=s["species"], t=_tn(d["type"], lang), mv=mv, z=zc[d["type"]]))
                    break
            if any(o["tag"] == "mechanic" and o["changes"].get("item", "").endswith(" Z") for o in out):
                break

    # 3) Huecos defensivos (tipo con >=3 débiles y más débiles que resistentes)
    holes = sorted(((t, d) for t, d in (matrix or {}).items() if d and d["weak_count"] >= 3 and d["weak_count"] > d["resist_count"]),
                   key=lambda td: td[1]["weak_count"] - td[1]["resist_count"], reverse=True)
    hole_done = False
    if holes:
        t, d = holes[0]
        names = ", ".join(w["species"] for w in d["weak"][:4])
        if mech.get("allow_tera"):  # Teratipo: lo más barato, no cambia el equipo
            for s in slots:
                if s.get("tera_type") or nid(s["species"]) in touched or not any(w["species"] == s["species"] for w in d["weak"]):
                    continue
                for tt in TYPE_NAMES:
                    m = compute_defensive_matchups([tt], "")
                    if t in (m["x05"] + m["x025"] + m["x0"]) and tt in (ent(s).get("types") or []) + ["Steel", "Fairy", "Water", "Fire"]:
                        add("set", "defense", s, None, {"tera_type": tt}, _t("tera", lang, n=d["weak_count"], t=_tn(t, lang), tt=_tn(tt, lang), s=s["species"]))
                        hole_done = True
                        break
                if hole_done:
                    break
        if not hole_done:
            weak_members = [s for s in slots if any(w["species"] == s["species"] for w in d["weak"]) and nid(s["species"]) not in touched
                            and not unique_role_owner(s["species"])]
            for cand, rank in ranked[:80]:
                m = compute_defensive_matchups(cand.get("types", []), (legal_abilities(cand, gen) or [""])[0])
                if t not in (m["x05"] + m["x025"] + m["x0"]) or not weak_members:
                    continue
                tgt = min(weak_members, key=lambda s: bst(ent(s)))
                if swap_ok(tgt, cand):
                    mult = "x0" if t in m["x0"] else ("x0.25" if t in m["x025"] else "x0.5")
                    add("replace", "defense", tgt, cand["name"], {}, _t("hole", lang, names=names, t=_tn(t, lang), k=d["resist_count"], c=cand["name"], u=f"{mult}, {usage_txt(rank)}", s=tgt["species"]))
                    hole_done = True
                    break

    # 4) Roles que faltan (según el tipo de formato)
    have = set().union(*[_roles_of(s) for s in slots])
    have_roles = have
    ks = set().union(*[_keys(s) for s in slots])
    if "k:setter" in ks and "k:abuser" in ks:
        have.add("speed")  # clima/terreno + beneficiario (Sol + Clorofila, Lluvia + Nado Rápido...) ya es control de velocidad
    STRONG = {"speed", "fakeout", "hazards", "removal"}
    gaps = [r for r in WANTED[doubles] if r not in have]

    # 4a) Protect en dobles: casi obligatorio salvo con objeto Choice
    if doubles and "protect" in lm and "protect" not in R["ban"]:
        for s in slots:
            has_protect = any(nid(m) in {"protect", "detect", "kingsshield", "spikyshield", "banefulbunker", "silktrap", "burningbulwark"} for m in s["moves"])
            learn = full_learnset(ent(s))
            if has_protect or "protect" not in learn or len(s["moves"]) < 4 or nid(s["species"]) in touched:
                continue
            if "choice" in nid(s.get("item") or ""):
                continue
            stab = set(ent(s).get("types", []))
            dmg = [m for m in s["moves"] if lm.get(nid(m), {}).get("category") != "Status"]
            low = sorted(s["moves"], key=lambda m: (lm.get(nid(m), {}).get("category") != "Status", _bp(lm.get(nid(m), {}).get("basePower")) * (1.5 if lm.get(nid(m), {}).get("type") in stab else 1.0)))
            is_st = lambda m: lm.get(nid(m), {}).get("category") == "Status"
            old = next((m for m in low if (is_st(m) and nid(m) not in KEEP_STATUS) or (not is_st(m) and len(dmg) >= 3)), None)
            if old:
                add("set", "role", s, None, {"moves": [("Protect" if m == old else m) for m in s["moves"]]}, _t("protect", lang, s=s["species"], old=old))
                break

    # 4b) Roles que faltan (los opcionales solo si no hay nada más importante que decir)
    gaps = [r for r in gaps if r in STRONG or not out]
    for r in gaps[:2]:
        ms, abs_, labels = ROLES[r]
        label = labels[_L.get(lang, 0)]
        done = False
        if ms:  # (a) un miembro que ya puede aprender el movimiento: cambio mínimo de set
            for s in slots:
                if nid(s["species"]) in touched or len(s["moves"]) < 4:
                    continue
                learn = full_learnset(ent(s))
                opts = [m for m in ms if m in learn and _move_ok(m, learn, pool, R)]
                if not opts:
                    continue
                keep = {nid(m) for m in s["moves"]}
                stab = set(ent(s).get("types", []))
                dmg = [m for m in s["moves"] if lm.get(nid(m), {}).get("category") != "Status"]

                def value(m: str) -> float:
                    d = lm.get(nid(m), {})
                    if nid(m) in {"protect", "detect"} or any(nid(m) in x[0] for x in ROLES.values()):
                        return 1000
                    if d.get("category") == "Status":
                        return 40
                    return _bp(d.get("basePower")) * (1.5 if d.get("type") in stab else 1.0)

                cand_old = sorted(s["moves"], key=value)
                old = next((m for m in cand_old if lm.get(nid(m), {}).get("category") == "Status" or len(dmg) >= 3), None)
                if old and value(old) < 1000:
                    new_mv = lm[sorted(opts)[0]]["name"]
                    add("set", "role", s, None, {"moves": [new_mv if m == old else m for m in s["moves"]]},
                        _t("role_move", lang, r=label, s=s["species"], mv=new_mv, old=old))
                    done = True
                    break
        if not done:  # (b) sustituir a un miembro por un Pokémon legal y de uso real que aporte el rol
            for cand, rank in ranked[:120]:
                learn = full_learnset(cand)
                mv = sorted(m for m in ms if m in learn and _move_ok(m, learn, pool, R))
                ok_ab = any(nid(a) in abs_ for a in legal_abilities(cand, gen))
                tgt = weakest(touched)
                if not (mv or ok_ab) or not tgt or not swap_ok(tgt, cand):
                    continue
                how = lm[mv[0]]["name"] if mv else next(a for a in legal_abilities(cand, gen) if nid(a) in abs_)
                add("replace", "role", tgt, cand["name"], {}, _t("role_swap", lang, r=label, c=cand["name"], mv=how, u=usage_txt(rank), s=tgt["species"]))
                break

    # 5) Cobertura ofensiva
    types = [x for x in chart if x in TYPE_NAMES]
    hit = {d for s in slots for mv in s["moves"] for d in types
           if lm.get(nid(mv), {}).get("category") != "Status" and chart.get(lm.get(nid(mv), {}).get("type"), {}).get(d, 1) >= 2}
    miss = [x for x in types if x not in hit]
    if len(miss) >= 3 and len(out) < 8:
        best = None
        for s in slots:
            if nid(s["species"]) in touched or len(s["moves"]) < 4:
                continue
            e, learn = ent(s), full_learnset(ent(s))
            phys = (e.get("baseStats") or {}).get("atk", 0) >= (e.get("baseStats") or {}).get("spa", 0)
            have_t = {lm.get(nid(m), {}).get("type") for m in s["moves"]}
            for mid in learn:
                d = lm.get(mid)
                if not d or d.get("category") != ("Physical" if phys else "Special") or _bp(d.get("basePower")) < 70 or d.get("type") in have_t:
                    continue
                if not _move_ok(mid, learn, pool, R):
                    continue
                cov = [x for x in miss if chart.get(d["type"], {}).get(x, 1) >= 2]
                dmg = [m for m in s["moves"] if lm.get(nid(m), {}).get("category") != "Status"]
                if len(cov) >= 2 and len(dmg) >= 3 and (best is None or (len(cov), _bp(d["basePower"])) > best[0]):
                    best = ((len(cov), _bp(d["basePower"])), s, d["name"], cov, dmg)
        if best:
            _, s, mv, cov, dmg = best
            stab = set(ent(s).get("types", []))
            old = min(dmg, key=lambda m: _bp(lm[nid(m)].get("basePower")) * (1.5 if lm[nid(m)].get("type") in stab else 1.0))
            add("set", "coverage", s, None, {"moves": [mv if m == old else m for m in s["moves"]]},
                _t("cover", lang, types=", ".join(_tn(x, lang) for x in miss[:6]), mv=mv, s=s["species"], cov=", ".join(_tn(x, lang) for x in cov)))

    # 6) Consejos: hechos verificables del equipo y del formato (sin inventar efectos)
    L = _L.get(lang, 0)
    sp_of = lambda s_: int((s_.get("final_stats") or {}).get("speed", 0))
    tips: List[str] = []
    mech_parts = []
    mega_slot = next((s_ for s_ in slots if ent(s_).get("is_mega")), None)
    if mega_slot and mech.get("allow_megas"):
        mech_parts.append(_t("tip_mega", lang, f=fmt, m=mega_slot["species"]))
    if mech.get("allow_tera"):
        tl = [f"{s_['species']} ({_tn(s_['tera_type'], lang)})" for s_ in slots if s_.get("tera_type") in TYPE_NAMES]
        mech_parts.append(_t("tip_tera", lang, l=", ".join(tl)) if tl else _t("tip_tera_none", lang))
    if mech.get("allow_z_moves"):
        zl = [f"{s_['species']} ({s_['item']})" for s_ in slots if legal_items.get(nid(s_.get("item") or ""), {}).get("isZ")]
        if zl:
            mech_parts.append(_t("tip_z", lang, l=", ".join(zl)))
    if mech.get("allow_dynamax"):
        mech_parts.append(_t("tip_dyna", lang, s=max(slots, key=lambda s_: bst(ent(s_)))["species"]))
    if mech_parts:
        tips.append(" ".join(mech_parts))

    setters = [s_ for s_ in slots if nid(s_.get("ability") or "") in _SETTERS]
    abusers = [s_["species"] for s_ in slots if nid(s_.get("ability") or "") in _ABUSERS]
    if setters and abusers:
        wmap = {"drought": ("Sol", "Sun", "Soleil"), "orichalcumpulse": ("Sol", "Sun", "Soleil"), "drizzle": ("Lluvia", "Rain", "Pluie"),
                "sandstream": ("Tormenta de arena", "Sandstorm", "Tempête de sable"), "snowwarning": ("Nieve", "Snow", "Neige"),
                "grassysurge": ("Campo de Hierba", "Grassy Terrain", "Champ Herbu"), "electricsurge": ("Campo Eléctrico", "Electric Terrain", "Champ Électrifié"),
                "hadronengine": ("Campo Eléctrico", "Electric Terrain", "Champ Électrifié"), "psychicsurge": ("Campo Psíquico", "Psychic Terrain", "Champ Psychique"),
                "mistysurge": ("Campo de Niebla", "Misty Terrain", "Champ Brumeux")}
        st = setters[0]
        tips.append(_t("tip_weather", lang, st=st["species"], w=wmap.get(nid(st.get("ability") or ""), ("clima", "weather", "météo"))[L], ab=", ".join(abusers)))

    weak = sorted(((t, d) for t, d in (matrix or {}).items() if d and d["weak_count"] >= 2), key=lambda td: td[1]["weak_count"], reverse=True)[:3]
    if weak:
        tips.append(_t("tip_weak", lang, l="; ".join(f"{_tn(t, lang)} ({d['weak_count']}: {', '.join(w['species'] for w in d['weak'][:3])})" for t, d in weak)))

    if len(slots) >= 2 and all(sp_of(s_) for s_ in slots):
        order = sorted(slots, key=sp_of, reverse=True)
        src_ = [f"{s_['species']} ({lm[m]['name']})" for s_ in slots for m in (nid(x) for x in s_["moves"]) if m in ROLES["speed"][0] and m in lm]
        if "k:setter" in ks and "k:abuser" in ks:
            src_ += [f"{x['species']} ({x.get('ability')})" for x in slots if nid(x.get("ability") or "") in _ABUSERS]
        sc = _t("sc_yes", lang, r=", ".join(src_[:4])) if src_ else _t("sc_no", lang)
        tips.append(_t("tip_speed", lang, o=" > ".join(f"{s_['species']} ({sp_of(s_)})" for s_ in order), sc=sc))

    clauses = []
    fid_ = nid(pool["format"].get("id", ""))
    if "vgc" in fid_:
        clauses.append(_t("r_pick", lang, n=4))
    elif "bss" in fid_ or "battlestadium" in fid_:
        clauses.append(_t("r_pick", lang, n=3))
    if R["item_clause"]:
        clauses.append(_t("r_item", lang))
    if R["ohko"]:
        clauses.append(_t("r_ohko", lang))
    if R["evasion"]:
        clauses.append(_t("r_eva", lang))
    if R["sleep"]:
        clauses.append(_t("r_sleep", lang))
    if mech.get("max_restricted"):
        clauses.append(_t("r_restr", lang, n=mech["max_restricted"]))
    if clauses:
        tips.append(_t("tip_rules", lang, f=fmt, r="; ".join(clauses)))

    dmg_side = {"Physical": 0, "Special": 0}
    for s_ in slots:
        cats = [lm.get(nid(m), {}).get("category") for m in s_["moves"]]
        dmg_side["Physical" if cats.count("Physical") >= cats.count("Special") else "Special"] += 1 if (cats.count("Physical") + cats.count("Special")) else 0
    ph, sp_ = dmg_side["Physical"], dmg_side["Special"]
    if len(slots) >= 4 and (ph >= 5 or sp_ >= 5) and min(ph, sp_) <= 1:
        major, minor = ("phys", "spec") if ph > sp_ else ("spec", "phys")
        tips.append(_t("tip_off", lang, a=_T[major][L], b=_T[minor][L], a2=_T[major][L], n=max(ph, sp_)))

    # Límites por sección: reemplazos, ajustes de set y consejos
    reps = [o for o in out if o["type"] in ("replace", "mega")][:3]
    sets = [o for o in out if o["type"] in ("set", "fix")][:4]
    notes_ = [{"type": "note", "tag": "tip", "target": None, "add": None, "changes": {}, "reason": t} for t in tips[:3]]
    return reps + sets + notes_
