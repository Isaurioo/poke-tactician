"""
Arquetipos adaptados a lo que EXISTE en cada generación y formato. Nada de listas fijas de nombres: se calcula quién puede
activar cada mecánica (por habilidad o por movimiento legal en esa generación) y, con eso, se comprueba si lo pedido es
posible, se adapta o se rechaza, se puntúa a los candidatos y, al final, se verifica qué se logró de verdad.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.era_rules import legal_abilities
from src.core.gen_data import gen_learnset
from src.core.messages import msg
from src.core.team_validator import BOOST_MOVES

nid = lambda x: re.sub(r"[^a-z0-9]", "", str(x).lower())
_L = {"es": 0, "en": 1, "fr": 2}

# clave: (tipo, movimientos, habilidades, solo_dobles, etiqueta es/en/fr)
FEATURES: Dict[str, Dict[str, Any]] = {
    "rain": dict(kind="weather", moves={"raindance"}, abil={"drizzle"}, label=("Lluvia", "Rain", "Pluie")),
    "sun": dict(kind="weather", moves={"sunnyday"}, abil={"drought", "orichalcumpulse"}, label=("Sol", "Sun", "Soleil")),
    "sand": dict(kind="weather", moves={"sandstorm"}, abil={"sandstream"}, label=("Tormenta de arena", "Sandstorm", "Tempête de sable")),
    "snow": dict(kind="weather", moves={"hail", "snowscape", "chillyreception"}, abil={"snowwarning"}, label=("Nieve/Granizo", "Snow/Hail", "Neige/Grêle")),
    "grassy": dict(kind="terrain", moves={"grassyterrain"}, abil={"grassysurge"}, label=("Campo de Hierba", "Grassy Terrain", "Champ Herbu")),
    "electric": dict(kind="terrain", moves={"electricterrain"}, abil={"electricsurge", "hadronengine"}, label=("Campo Eléctrico", "Electric Terrain", "Champ Électrifié")),
    "psychic": dict(kind="terrain", moves={"psychicterrain"}, abil={"psychicsurge"}, label=("Campo Psíquico", "Psychic Terrain", "Champ Psychique")),
    "misty": dict(kind="terrain", moves={"mistyterrain"}, abil={"mistysurge"}, label=("Campo de Niebla", "Misty Terrain", "Champ Brumeux")),
    "trickroom": dict(kind="speed", moves={"trickroom"}, abil=set(), label=("Trick Room", "Trick Room", "Distorsion")),
    "tailwind": dict(kind="speed", moves={"tailwind"}, abil=set(), label=("Tailwind", "Tailwind", "Vent Arrière")),
    "hazards": dict(kind="role", moves={"stealthrock", "spikes", "toxicspikes", "stickyweb"}, abil=set(), label=("trampas (hazards)", "entry hazards", "pièges (hazards)")),
    "redirect": dict(kind="role", moves={"followme", "ragepowder"}, abil=set(), doubles=True, label=("redirección", "redirection", "redirection")),
    "screens": dict(kind="role", moves={"reflect", "lightscreen", "auroraveil"}, abil=set(), label=("pantallas", "screens", "écrans")),
    "pivot": dict(kind="role", moves={"uturn", "voltswitch", "flipturn", "partingshot", "teleport", "batonpass"}, abil=set(), label=("pivoteo", "pivoting", "pivot")),
    "setup": dict(kind="role", moves=set(BOOST_MOVES), abil=set(), label=("setup", "setup", "setup")),
    "perish": dict(kind="role", moves={"perishsong"}, abil=set(), label=("Perish Song", "Perish Song", "Perish Song")),
    "trap": dict(kind="role", moves={"meanlook", "block", "spiderweb"}, abil={"shadowtag", "arenatrap", "magnetpull"}, label=("atrapadores", "trappers", "piégeurs")),
}
ABUSERS = {  # habilidades que de verdad se benefician del efecto
    "rain": {"swiftswim"}, "sun": {"chlorophyll", "solarpower", "protosynthesis"}, "sand": {"sandrush", "sandforce"},
    "snow": {"slushrush"}, "grassy": {"grasspelt"}, "electric": {"surgesurfer", "quarkdrive"}, "psychic": set(), "misty": set(),
}
TYPE_MIN_GEN = {"Dark": 2, "Steel": 2, "Fairy": 6}
TYPE_WORDS = {
    "Normal": ("normal",), "Fire": ("fuego", "fire", "feu"), "Water": ("agua", "water", "eau"), "Grass": ("planta", "hierba", "grass", "plante"),
    "Electric": ("electrico", "electric", "electrik"), "Ice": ("hielo", "ice", "glace"), "Fighting": ("lucha", "fighting", "combat"),
    "Poison": ("veneno", "poison"), "Ground": ("tierra", "ground", "terre"), "Flying": ("volador", "flying", "vol"),
    "Psychic": ("psiquico", "psychic", "psy"), "Bug": ("bicho", "bug", "insecte"), "Rock": ("roca", "rock", "roche"),
    "Ghost": ("fantasma", "ghost", "spectre"), "Dragon": ("dragon",), "Dark": ("siniestro", "dark", "tenebres"),
    "Steel": ("acero", "steel", "acier"), "Fairy": ("hada", "fairy", "fee"),
}
_INTENT_FEATURES = {  # flag de intención -> características que exige
    "wants_rain": ["rain"], "wants_sun": ["sun"], "wants_sand": ["sand"], "wants_snow": ["snow"],
    "wants_grassy": ["grassy"], "wants_electric": ["electric"], "wants_psychic": ["psychic"], "wants_misty": ["misty"],
    "wants_tr": ["trickroom"], "wants_tailwind": ["tailwind"], "wants_hazards": ["hazards"], "wants_redirect": ["redirect"],
    "wants_screens": ["screens"], "wants_pivot": ["pivot"], "wants_setup": ["setup"], "wants_perish_trap": ["perish", "trap"],
}


def parse_core_types(text: str) -> List[str]:
    """Tipos pedidos como núcleo ('core Fuego-Agua-Planta') en español, inglés o francés."""
    import unicodedata
    n = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
    m = re.search(r"\b(core|nucleo|noyau)\b(.{0,70})", n)
    if not m:
        return []
    out: List[str] = []
    for w in re.findall(r"[a-z]+", m.group(2)):
        for t, words in TYPE_WORDS.items():
            if w in words and t not in out:
                out.append(t)
    return out if len(out) >= 2 else []


def supply(pool: Dict[str, Any], key: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(especies con la habilidad, especies que aprenden el movimiento) legales en este formato y generación."""
    cache = pool.setdefault("_feat_cache", {})
    if key in cache:
        return cache[key]
    f, gen = FEATURES[key], int(pool["mechanics"].get("gen", 9) or 9)
    ban = {nid(b) for b in pool["format"].get("banlist", [])}
    lm = pool["legal_moves"]
    moves = {m for m in f["moves"] if m in lm}
    abil = {a for a in f["abil"] if a not in ban}
    ab_users, mv_users = [], []
    for e in pool["legal_pokemon"].values():
        if gen >= 3 and abil & {nid(a) for a in legal_abilities(e, gen)}:
            ab_users.append(e)
        elif moves and moves & gen_learnset(e, gen):
            mv_users.append(e)
    cache[key] = (ab_users, mv_users)
    return cache[key]


def _label(key: str, lang: str) -> str:
    return FEATURES[key]["label"][_L.get(lang, 0)]


def required_features(intent: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for flag, keys in _INTENT_FEATURES.items():
        if intent.get(flag):
            out += [k for k in keys if k not in out]
    return out


def check_request(intent: Dict[str, Any], pool: Dict[str, Any], lang: str) -> Tuple[List[str], List[str]]:
    """(errores, adaptaciones) antes de construir: ¿existe lo pedido en este formato y generación?"""
    fmt, gen = pool["format"]["name"], int(pool["mechanics"].get("gen", 9) or 9)
    doubles = pool["format"].get("game_type") == "doubles"
    errors: List[str] = []
    notes: List[str] = []
    feats = required_features(intent)
    if intent.get("wants_perish_trap"):
        _, pm = supply(pool, "perish")
        pa, pmv = supply(pool, "perish")
        ta, tm = supply(pool, "trap")
        if not (pa or pmv) or not (ta or tm):
            errors.append(msg("ft_perish", lang, f=fmt))
        feats = [k for k in feats if k not in ("perish", "trap")]
    for k in feats:
        f = FEATURES[k]
        if f.get("doubles") and not doubles:
            errors.append(msg("ft_doubles", lang, w=_label(k, lang), f=fmt))
            continue
        ab, mv = supply(pool, k)
        if not ab and not mv:
            errors.append(msg("ft_none", lang, w=_label(k, lang), f=fmt))
        elif f["kind"] == "role" and k in ("pivot", "hazards", "screens", "redirect"):
            have_m = sorted(lm_name for m in f["moves"] if m in pool["legal_moves"] for lm_name in [pool["legal_moves"][m].get("name", m)])
            if len(have_m) < len(f["moves"]):
                notes.append(msg("ft_avail", lang, f=fmt, w=_label(k, lang), m=", ".join(have_m)))
        elif f["kind"] in ("weather", "terrain") and not ab and mv:
            names = ", ".join(sorted(m for m in f["moves"] if m in pool["legal_moves"]))
            notes.append(msg("ft_move_only", lang, w=_label(k, lang), f=fmt, m=names))
    k_req = int(intent.get("wants_restricted_n") or 0)
    if k_req:
        cap = int(pool["mechanics"].get("max_restricted", 0) or 0)
        if cap == 0:
            errors.append(msg("ft_restr_none", lang, f=fmt))
        elif cap < k_req:
            notes.append(msg("ft_restr_cap", lang, f=fmt, n=cap, k=k_req))
    for t in intent.get("core_types", []):
        if TYPE_MIN_GEN.get(t, 1) > gen:
            errors.append(msg("ft_type", lang, t=t, f=fmt, g=gen))
    if intent.get("wants_dual_weather"):
        avail = [k for k in ("rain", "sun", "sand", "snow") if any(supply(pool, k))]
        if len(avail) == 1:
            notes.append(msg("ft_dual", lang, f=fmt, w=_label(avail[0], lang)))
        elif not avail:
            errors.append(msg("ft_none", lang, w="Clima" if lang == "es" else ("Météo" if lang == "fr" else "Weather"), f=fmt))
    return errors, notes


def intent_bonus(entry: Dict[str, Any], intent: Dict[str, Any], pool: Dict[str, Any]) -> float:
    """Puntuación de relevancia para los arquetipos pedidos, calculada con lo disponible en el formato."""
    gen = int(pool["mechanics"].get("gen", 9) or 9)
    doubles = pool["format"].get("game_type") == "doubles"
    eid = nid(entry.get("name"))
    abil = {nid(a) for a in legal_abilities(entry, gen)} if gen >= 3 else set()
    learn = None
    bonus = 0.0
    lc_format = "lc" in nid(pool["format"].get("id", "")) or "littlecup" in nid(pool["format"].get("name", ""))
    fully = lc_format or str(entry.get("tier") or "").upper() not in ("NFE", "LC")
    keys = required_features(intent) if fully and sum((entry.get("baseStats") or {}).values()) >= 400 else []
    if intent.get("wants_dual_weather"):
        keys += [k for k in ("rain", "sun", "sand", "snow") if k not in keys and any(supply(pool, k))][:2]
    bs = entry.get("baseStats") or {}
    for k in keys:
        f = FEATURES[k]
        if f.get("doubles") and not doubles:
            continue
        ab_users, mv_users = supply(pool, k)
        if any(nid(u["name"]) == eid for u in ab_users):
            bonus += 3200.0
        elif any(nid(u["name"]) == eid for u in mv_users):
            bonus += 1400.0 if ab_users else 2400.0
        if k in ABUSERS and abil & ABUSERS[k] and (ab_users or mv_users):
            blocked = any((a in {nid(x) for x in FEATURES[k]["abil"]} and b in abil) or (b in {nid(x) for x in FEATURES[k]["abil"]} and a in abil)
                          for a, b, _ in _team_pairs(pool))
            if not blocked:
                bonus += 1800.0
    spe, atk, spa = bs.get("spe", 80), bs.get("atk", 80), bs.get("spa", 80)
    if intent.get("wants_ho"):
        bonus += max(0.0, (max(atk, spa) + spe - 150) * 8)
    if intent.get("wants_stall"):
        bonus += max(0.0, (bs.get("hp", 80) + bs.get("def", 80) + bs.get("spd", 80) - 260) * 10)
        if learn is None:
            learn = gen_learnset(entry, gen)
        if learn & {"recover", "roost", "softboiled", "slackoff", "wish", "synthesis", "moonlight", "morningsun", "milkdrink", "shoreup"}:
            bonus += 900.0
    for t in intent.get("core_types", []):
        if fully and sum(bs.values()) >= 400 and t in (entry.get("types") or []):
            bonus += 2800.0
    if intent.get("wants_gmax") and pool["mechanics"].get("allow_dynamax") and nid(entry.get("baseSpecies") or entry.get("name")) in GMAX_BASES:
        bonus += 3000.0
    return bonus


def _team_pairs(pool: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    from src.core.team_validator import _rules
    return _rules(pool)["team_pairs"]


def team_archetype(team: List[Dict[str, Any]], pool: Dict[str, Any]) -> str:
    """Etiqueta del arquetipo calculada con el equipo FINAL (no con lo que se pidió)."""
    ab = {nid(p.get("ability") or "") for p in team}
    mv = {nid(m) for p in team for m in p.get("moves", [])}
    has = lambda key: bool(FEATURES[key]["abil"] & ab) or bool(FEATURES[key]["moves"] & mv)
    if "perishsong" in mv and ((FEATURES["trap"]["abil"] & ab) or (FEATURES["trap"]["moves"] & mv)):
        return "Perish Trap"
    if "trickroom" in mv:
        return "Trick Room Offense"
    wx = [k for k in ("rain", "sun", "sand", "snow") if FEATURES[k]["abil"] & ab]
    if len(wx) >= 2:
        return "Dual Weather Offense"
    for key, name in (("rain", "Rain Offense"), ("sun", "Sun Offense"), ("sand", "Sand Offense"), ("snow", "Snow Offense")):
        if (FEATURES[key]["abil"] & ab):
            return name
    for key, name in (("grassy", "Grassy Terrain Offense"), ("electric", "Electric Terrain Offense"), ("psychic", "Psychic Terrain Offense"), ("misty", "Misty Terrain Offense")):
        if FEATURES[key]["abil"] & ab:
            return name
    for key, name in (("rain", "Rain Offense"), ("sun", "Sun Offense"), ("sand", "Sand Offense"), ("snow", "Snow Offense")):
        if FEATURES[key]["moves"] & mv:
            return name
    if "tailwind" in mv:
        return "Tailwind Offense"
    return "Balanced Offense"


def verify_outcome(intent: Dict[str, Any], team: List[Dict[str, Any]], pool: Dict[str, Any], lang: str) -> List[str]:
    """Avisos honestos sobre lo pedido que el equipo final no cumple."""
    notes: List[str] = []
    ab = {nid(p.get("ability") or "") for p in team}
    mv = {nid(m) for p in team for m in p.get("moves", [])}
    for k in required_features(intent):
        if k in ("perish", "trap", "setup", "pivot", "hazards", "redirect", "screens"):
            continue
        f = FEATURES[k]
        if not ((f["abil"] & ab) or (f["moves"] & mv)) and any(supply(pool, k)):
            notes.append(msg("ut_feature", lang, w=_label(k, lang)))
    if intent.get("wants_perish_trap"):
        trap = (FEATURES["trap"]["abil"] & ab) or (FEATURES["trap"]["moves"] & mv)
        if "perishsong" not in mv or not trap:
            notes.append(msg("ut_perish", lang))
    core = intent.get("core_types", [])
    if core:
        have = {t for p in team for t in (p.get("types") or [])}
        miss = [t for t in core if t not in have and TYPE_MIN_GEN.get(t, 1) <= int(pool["mechanics"].get("gen", 9) or 9)]
        if miss:
            notes.append(msg("ut_core", lang, t=", ".join(miss)))
    return notes


_ROLE_KEEP = {"protect", "detect", "fakeout", "tailwind", "trickroom", "followme", "ragepowder", "helpinghand", "wideguard", "quickguard"}


MIN_COUNT = {"hazards": 2, "pivot": 2, "setup": 2}  # "Hazard Stacking", "pivoteo continuo", "Setup Sweepers": más de un miembro


def enforce_features(team: List[Dict[str, Any]], intent: Dict[str, Any], pool: Dict[str, Any], resolve: Any) -> None:
    """Si el equipo no trae una mecánica pedida (p. ej. Rain Dance en Gen 2), se la da a quien puede aprenderla."""
    gen = int(pool["mechanics"].get("gen", 9) or 9)
    doubles = pool["format"].get("game_type") == "doubles"
    lm = pool["legal_moves"]
    affinity_map = {"rain": {"Water"}, "sun": {"Fire", "Grass"}, "sand": {"Rock", "Ground", "Steel"}, "snow": {"Ice"},
                    "grassy": {"Grass"}, "electric": {"Electric"}, "psychic": {"Psychic"}, "misty": {"Fairy", "Dragon"}}
    for key in required_features(intent):
        f = FEATURES[key]
        if key == "trap" or (f.get("doubles") and not doubles):
            continue
        for _ in range(MIN_COUNT.get(key, 1)):
            ab = {nid(p.get("ability") or "") for p in team}
            has_move = [p for p in team if f["moves"] & {nid(m) for m in p.get("moves", [])}]
            if (f["abil"] & ab) and key not in MIN_COUNT:
                break
            if len(has_move) >= MIN_COUNT.get(key, 1) or (key not in MIN_COUNT and has_move):
                break
            best = None
            for slot in team:
                if slot in has_move:
                    continue
                e = resolve(slot["species"]) or {}
                opts = sorted(m for m in f["moves"] if m in lm and m in gen_learnset(e, gen))
                if not opts or "choice" in nid(slot.get("item") or ""):
                    continue
                stab = set(e.get("types", []))

                def value(m: str) -> float:
                    d = lm.get(nid(m), {})
                    if nid(m) in _ROLE_KEEP:
                        return 1000
                    if d.get("category") == "Status":
                        return 40
                    try:
                        bp = int(d.get("basePower") or 0)
                    except (TypeError, ValueError):
                        bp = 0
                    return bp * (1.5 if d.get("type") in stab else 1.0)

                dmg = [m for m in slot["moves"] if lm.get(nid(m), {}).get("category") != "Status"]
                cand = [m for m in slot["moves"] if value(m) < 1000 and (lm.get(nid(m), {}).get("category") == "Status" or len(dmg) > 2)]
                if len(slot["moves"]) < 4:
                    cand = [None]
                if not cand:
                    continue
                old = None if None in cand else min(cand, key=value)
                score = (0 if affinity_map.get(key, set()) & stab else 1, 0 if old is None else value(old))
                if best is None or score < best[0]:
                    best = (score, slot, old, lm[opts[0]]["name"])
            if not best:
                break
            _, slot, old, new = best
            slot["moves"] = [new if m == old else m for m in slot["moves"]] if old else slot["moves"] + [new]
            slot["_dirty"] = True


# Especies con forma Gigamax (Gen 8). Los datos no las traen: lista cerrada y oficial.
GMAX_BASES = {"venusaur", "charizard", "blastoise", "butterfree", "pikachu", "meowth", "machamp", "gengar", "kingler", "lapras", "eevee",
              "snorlax", "garbodor", "melmetal", "rillaboom", "cinderace", "inteleon", "corviknight", "orbeetle", "drednaw", "coalossal",
              "flapple", "appletun", "sandaconda", "toxtricity", "centiskorch", "hatterene", "grimmsnarl", "alcremie", "copperajah",
              "duraludon", "urshifu"}


def strip_gmax(names: List[str]) -> Tuple[List[str], bool]:
    """Quita el sufijo -Gmax que pudiera escribir el modelo: el Gigamax lo marca el motor, no el nombre."""
    out, found = [], False
    for n in names:
        m = re.sub(r"[-\s]*(gmax|gigantamax|gigamax)$", "", str(n), flags=re.I)
        found = found or m != str(n)
        out.append(m)
    return out, found


def _bst(e: Dict[str, Any]) -> int:
    return sum((e.get("baseStats") or e.get("base_stats") or {}).values())


def mark_gigantamax(team: List[Dict[str, Any]], pool: Dict[str, Any], wanted: bool, resolve: Any, lang: str) -> List[str]:
    """Marca el Gigamax del atacante principal (solo especies que lo tienen) y lo anuncia; si no hay ninguna, lo dice."""
    if not pool["mechanics"].get("allow_dynamax") or not wanted:
        return []
    cap = [p for p in team if nid((resolve(p["species"]) or {}).get("baseSpecies") or p["species"]) in GMAX_BASES]
    if not cap:
        return [msg("ut_gmax", lang)]
    best = max(cap, key=lambda p: _bst(p))
    best["gigantamax"] = True
    return [msg("gmax_pick", lang, s=best["species"])]


def mark_primal(team: List[Dict[str, Any]]) -> None:
    """Etiqueta `primal` a Groudon/Kyogre que llevan su orbe (Reversión Primigenia): no es Mega, es una forma de batalla."""
    for p in team:
        sp = nid(p.get("species", ""))
        item = p.get("item") or ""
        if (sp in ("groudon", "kyogre") and item in ("Red Orb", "Blue Orb")) or sp in ("groudonprimal", "kyogreprimal"):
            p["primal"] = True


NO_DYNAMAX_BASES = {"zacian", "zamazenta", "eternatus"}  # ni ellos ni sus formas pueden usar Dynamax (Bulbapedia/Serebii)


def mark_dynamax(team: List[Dict[str, Any]], pool: Dict[str, Any], wants_gmax: bool, resolve: Any, lang: str) -> List[str]:
    """Etiqueta al Pokémon que usará Dynamax (solo uno por combate), como la Mega, el cristal Z o la Teracristalización.
    Excluye a quienes no pueden Dynamax. Prefiere especies con Gigamax (+80 de puntaje) y las marca `gigantamax`."""
    if not pool["mechanics"].get("allow_dynamax") or not team:
        return []

    def base(p: Dict[str, Any]) -> str:
        return nid((resolve(p["species"]) or {}).get("baseSpecies") or p["species"])

    cands = [p for p in team if base(p) not in NO_DYNAMAX_BASES]
    if not cands:
        return []
    gm = [p for p in cands if base(p) in GMAX_BASES]
    if wants_gmax and not gm:
        notes = [msg("ut_gmax", lang)]
        pick = max(cands, key=_bst)
    else:
        pick = max(gm if wants_gmax else cands, key=lambda p: _bst(p) + (80 if base(p) in GMAX_BASES else 0))
        notes = []
    pick["dynamax"] = True
    if base(pick) in GMAX_BASES:
        pick["gigantamax"] = True
        notes.append(msg("gmax_pick", lang, s=pick["species"]))
    else:
        notes.append(msg("dyna_pick", lang, s=pick["species"]))
    return notes


_TERA_DEF = ["Steel", "Fairy", "Water", "Fire", "Normal", "Ghost", "Dragon", "Dark"]


def assign_tera_types(team: List[Dict[str, Any]], intent: Dict[str, Any], pool: Dict[str, Any], lang: str) -> List[str]:
    """Teratipo por defecto = su tipo; Ogerpon (máscara) y Terapagos (Estelar) tienen el suyo fijo; con 'defensivo', se elige para resistir."""
    from src.core.types import compute_defensive_matchups
    if not pool["mechanics"].get("allow_tera"):
        return []
    for p in team:
        sp = nid(p["species"])
        types = p.get("types") or []
        if sp.startswith("ogerpon") and len(types) > 1:
            p["tera_type"] = types[-1]
        elif sp.startswith("terapagos"):
            p["tera_type"] = "Stellar"
    notes: List[str] = []
    if not intent.get("wants_def_tera"):
        return notes
    counts: Dict[str, List[Dict[str, Any]]] = {}
    for p in team:
        m = compute_defensive_matchups(p.get("types") or [], p.get("ability") or "")
        for t in m["x4"] + m["x2"]:
            counts.setdefault(t, []).append(p)
    for t, members in sorted(counts.items(), key=lambda kv: -len(kv[1]))[:2]:
        if len(members) < 2:
            continue
        for p in sorted(members, key=lambda x: -_bst(x))[:1]:
            if nid(p["species"]).startswith(("ogerpon", "terapagos")):
                continue
            for tt in _TERA_DEF:
                m = compute_defensive_matchups([tt], "")
                if t in (m["x05"] + m["x025"] + m["x0"]):
                    p["tera_type"] = tt
                    notes.append(msg("tera_def", lang, s=p["species"], tt=tt, t=t, n=len(members)))
                    break
    return notes
