"""
Validador final de equipos: última barrera antes de responder.
Corrige lo corregible (movimientos, objetos, habilidades, EVs, naturaleza, Tera) y lanza
RuleViolation con lo que no se puede arreglar (especies, límite de Megas/restringidos...).
Se aplica también a sets heredados de turnos anteriores y a cambios pedidos por el usuario.
"""
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.core.messages import msg
from src.core.move_rules import PROTECT_FAMILY, drop_extra_protects
from src.services.smogon import normalize_id as nid

NATURES = {"hardy", "lonely", "brave", "adamant", "naughty", "bold", "docile", "relaxed", "impish", "lax",
           "timid", "hasty", "serious", "jolly", "naive", "modest", "mild", "quiet", "bashful", "rash",
           "calm", "gentle", "sassy", "careful", "quirky"}
TYPES = {"Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", "Ground", "Flying",
         "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy", "Stellar"}
OHKO = {"fissure", "guillotine", "horndrill", "sheercold"}
EVASION_MOVES = {"doubleteam", "minimize"}
EVASION_ITEMS = {"brightpowder", "laxincense"}
EVASION_ABILITIES = {"sandveil", "snowcloak"}
SLEEP_MOVES = {"spore", "sleeppowder", "hypnosis", "lovelykiss", "sing", "grasswhistle", "darkvoid", "yawn"}
SAFE_ITEMS = ["Sitrus Berry", "Lum Berry", "Leftovers", "Focus Sash", "Life Orb", "Assault Vest",
              "Safety Goggles", "Mental Herb", "Covert Cloak", "Shell Bell", "Choice Scarf"]


class RuleViolation(Exception):
    pass


def _pts(ev: int) -> int:
    return 0 if ev <= 0 else (ev + 4) // 8


def trim_evs(evs: Dict[str, int], champions: bool, protected: Optional[Set[str]] = None) -> Dict[str, int]:
    """Recorta el exceso de EVs (510) o de puntos Champions (66) empezando por lo que NO está protegido."""
    evs = {k: max(0, min(252, int(v))) for k, v in evs.items()}
    protected = protected or set()
    total = (lambda: sum(_pts(v) for v in evs.values())) if champions else (lambda: sum(evs.values()))
    cap = 66 if champions else 510
    while total() > cap:
        pool_ = [k for k in evs if evs[k] > 0 and k not in protected] or [k for k in evs if evs[k] > 0]
        k = max(pool_, key=evs.get)
        evs[k] = max(0, ((_pts(evs[k]) - 1) * 8 - 4)) if champions else max(0, evs[k] - 4)
        if champions and evs[k] < 0:
            evs[k] = 0
    return evs


def full_learnset(entry: Optional[Dict[str, Any]]) -> Set[str]:
    """Movimientos legales de una especie: propios + forma base + toda su cadena de preevoluciones."""
    from src.services import pokedex_service as pds
    pds._load_compendium_files()
    cache, extra = pds._POKEDEX_CACHE, pds._POKE_EXTRA
    out: Set[str] = set()
    seen: Set[str] = set()
    stack = [entry]
    while stack:
        e = stack.pop()
        if not e:
            continue
        eid = nid(e.get("id") or e.get("name"))
        if eid in seen:
            continue
        seen.add(eid)
        out |= {nid(m) for m in e.get("learnset") or []}
        base = e.get("baseSpecies")
        if base and nid(base) != eid:
            stack.append(cache.get(nid(base)))
        prevo = (extra.get(eid) or {}).get("prevo")
        if prevo:
            stack.append(cache.get(nid(prevo)))
    return out


def _rules(pool: Dict[str, Any]) -> Dict[str, Any]:
    fmt = pool["format"]
    rs = " ".join(fmt.get("ruleset", [])).lower()
    fid = nid(fmt.get("id", ""))
    short = "flat rules" in rs or any(k in fid for k in ("vgc", "bss", "battlestadium", "battlespot", "gbu"))
    standard = not short
    banset = {nid(b) for b in fmt.get("banlist", [])}
    mech = pool["mechanics"]
    return {
        "ban": banset,
        "ohko": standard or "ohko clause" in rs,
        "evasion": standard or "evasion" in rs,
        "sleep": "sleep moves clause" in rs,
        "item_clause": bool(mech.get("item_clause")) or "item clause" in rs or "flat rules" in rs,
        "evasion_ab": standard or "evasion abilities clause" in rs,
    }


def _move_ok(mid: str, learn: Set[str], pool: Dict[str, Any], R: Dict[str, Any]) -> bool:
    if mid not in pool["legal_moves"] or mid in R["ban"]:
        return False
    if R["ohko"] and mid in OHKO:
        return False
    if R["evasion"] and mid in EVASION_MOVES:
        return False
    return not learn or mid in learn


def _fill_move(entry: Dict[str, Any], learn: Set[str], have: Set[str], pool: Dict[str, Any],
               R: Dict[str, Any], is_doubles: bool, sleep_used: bool) -> Optional[str]:
    """Mejor reemplazo legal: Protect en dobles si falta; si no, ataque STAB de más poder."""
    lm = pool["legal_moves"]
    cands = [m for m in learn if m not in have and _move_ok(m, learn, pool, R)
             and not (R["sleep"] and sleep_used and m in SLEEP_MOVES)]
    if is_doubles and not (have & PROTECT_FAMILY):
        for m in ("protect", "detect"):
            if m in cands:
                return lm[m].get("name", m)
    stab = set(entry.get("types") or [])

    def score(m: str) -> Tuple[int, int]:
        d = lm.get(m, {})
        bp = d.get("basePower") or 0
        return (1 if d.get("type") in stab else 0, bp if isinstance(bp, int) else 0)

    cands.sort(key=score, reverse=True)
    return lm[cands[0]].get("name", cands[0]) if cands else None


def validate_team(
    team: List[Dict[str, Any]],
    pool: Dict[str, Any],
    resolve: Callable[[str], Optional[Dict[str, Any]]],
    max_megas: int,
    lang: str = "es",
    rank: Optional[List[int]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    from src.core.coverage import (get_ability_description_es, get_item_description_es,
                                   get_move_rich_details, get_nature_description_es)
    from src.core.era_rules import legal_abilities
    from src.core.optimizer import calculate_level_50_stats, compute_accurate_role_label
    from src.services.teambuilder import WEATHER_ABILITIES

    mech, fmt_name = pool["mechanics"], pool["format"]["name"]
    gen = int(mech.get("gen", 9) or 9)
    is_doubles = pool["format"].get("game_type") == "doubles"
    R = _rules(pool)
    legal_items = pool["legal_items"]
    notes: List[str] = []
    fatal: List[str] = []

    entries = [resolve(s.get("species", "")) for s in team]
    # --- reglas de equipo no corregibles ---
    bases: Set[str] = set()
    megas = restricted = 0
    for slot, e in zip(team, entries):
        if not e:
            fatal.append(slot.get("species", "?"))
            continue
        b = nid(e.get("baseSpecies") or e.get("name"))
        if b in bases:
            fatal.append(f"{slot['species']} (Species Clause)")
        bases.add(b)
        megas += bool(e.get("is_mega"))
        restricted += bool(e.get("is_restricted"))
    if megas > max_megas:
        fatal.append(f"{megas} Megas > {max_megas}")
    if mech.get("max_restricted", 0) and restricted > mech["max_restricted"]:
        fatal.append(f"{restricted} restricted > {mech['max_restricted']}")
    if fatal:
        raise RuleViolation(msg("rule_violation", lang, f=fmt_name, n=", ".join(fatal)))

    used_items: Set[str] = set()
    sleep_used = False
    # Orden de proceso: primero lo que el usuario pidió, luego lo que no se toca, al final lo nuevo.
    # Así, ante un choque (objeto repetido, etc.) siempre cede el último y no lo que el usuario fijó.
    order = sorted(range(len(team)), key=lambda i: (rank[i] if rank else 0))
    for i in order:
        slot, e = team[i], entries[i]
        sp = slot["species"]
        before = (slot.get("item"), slot.get("ability"), tuple(slot.get("moves") or []), slot.get("nature"), tuple(sorted((slot.get("evs") or {}).items())))

        # ---- Objeto ----
        if mech.get("allow_items", gen > 1) and gen > 1:
            item = slot.get("item") or ""
            iid = nid(item)
            req = e.get("requiredItem") if isinstance(e.get("requiredItem"), str) else None
            stone = next((v["name"] for v in legal_items.values() if v.get("megaStone")
                          and nid(v["megaStone"]) in (nid(e["name"]), nid(sp))), None) if e.get("is_mega") else None
            forced = req or stone
            it_obj = legal_items.get(iid, {})
            bad = (
                (forced and iid != nid(forced))
                or iid not in legal_items
                or (it_obj.get("megaStone") and not e.get("is_mega"))
                or (R["evasion"] and iid in EVASION_ITEMS)
                or (R["item_clause"] and iid in used_items)
            )
            if bad:
                new = forced
                if not new:
                    new = next((n for n in SAFE_ITEMS if nid(n) in legal_items and nid(n) not in used_items
                                and not (R["evasion"] and nid(n) in EVASION_ITEMS)), None)
                if not new:
                    new = next((v["name"] for k, v in legal_items.items() if not v.get("megaStone")
                                and not v.get("isZ") and k not in used_items), item)
                notes.append(msg("fix_item", lang, s=sp, a=item or "-", b=new))
                slot["item"] = new
            used_items.add(nid(slot["item"]))
        elif gen == 1:
            slot["item"] = None

        # ---- Habilidad ----
        if gen >= 3:
            abil = slot.get("ability") or ""
            options = legal_abilities(e, gen)

            def ab_bad(a: str) -> bool:
                return nid(a) in R["ban"] or (R["evasion_ab"] and nid(a) in EVASION_ABILITIES)

            if options and (abil not in options or ab_bad(abil)):
                good = [a for a in options if not ab_bad(a)]
                if not good:
                    raise RuleViolation(msg("rule_violation", lang, f=fmt_name, n=f"{sp}: {abil}"))
                notes.append(msg("fix_ability", lang, s=sp, a=abil or "-", b=good[0]))
                slot["ability"] = good[0]

        # ---- Movimientos ----
        learn = full_learnset(e)
        lm = pool["legal_moves"]
        kept: List[str] = []
        for mv in slot.get("moves") or []:
            mid = nid(mv)
            if mid in {nid(k) for k in kept}:
                continue
            if not _move_ok(mid, learn, pool, R) or (R["sleep"] and sleep_used and mid in SLEEP_MOVES):
                have = {nid(k) for k in kept} | {nid(x) for x in slot["moves"]}
                rep = _fill_move(e, learn, have, pool, R, is_doubles, sleep_used)
                if rep:
                    notes.append(msg("fix_move", lang, s=sp, a=mv, b=rep))
                    kept.append(rep)
                else:
                    notes.append(msg("fix_drop_move", lang, s=sp, a=mv))
                continue
            if R["sleep"] and mid in SLEEP_MOVES:
                sleep_used = True
            kept.append(lm[mid].get("name", mv) if mid in lm else mv)
        slot["moves"] = drop_extra_protects(kept)[:4]
        while len(slot["moves"]) < 4:  # sets incompletos: completar con movimientos legales
            have = {nid(m) for m in slot["moves"]}
            rep = _fill_move(e, learn, have, pool, R, is_doubles, sleep_used)
            if not rep:
                break
            slot["moves"].append(rep)

        # ---- Naturaleza / EVs / Tera ----
        if gen >= 3:
            if nid(slot.get("nature") or "") not in NATURES:
                slot["nature"] = "Serious"
            evs = trim_evs(slot.get("evs") or {}, "champions" in nid(pool["format"].get("id", "")))
            slot["evs"] = evs
        if not mech.get("allow_tera"):
            slot["tera_type"] = None
        elif slot.get("tera_type") not in TYPES:
            slot["tera_type"] = (slot.get("types") or [None])[0]

        # ---- Refrescar datos derivados si algo cambió ----
        after = (slot.get("item"), slot.get("ability"), tuple(slot["moves"]), slot.get("nature"), tuple(sorted((slot.get("evs") or {}).items())))
        if after != before:
            d = slot.setdefault("details", {})
            d["item_desc"] = get_item_description_es(slot["item"], e.get("baseSpecies", sp), gen) if slot.get("item") else ""
            d["ability_desc"] = get_ability_description_es(slot["ability"], gen) if slot.get("ability") else ""
            d["moves_info"] = [get_move_rich_details(m, lm, gen) for m in slot["moves"]]
            if gen >= 3:
                d["nature_desc"] = get_nature_description_es(slot["nature"])
                if slot.get("base_stats"):
                    slot["final_stats"] = calculate_level_50_stats(slot["base_stats"], slot["evs"], slot["nature"])
                try:
                    slot["role"] = compute_accurate_role_label(e, slot.get("ability"), slot["moves"], slot["evs"], WEATHER_ABILITIES)
                except Exception:
                    pass
    return team, notes


def audit_team(
    team: List[Dict[str, Any]],
    pool: Dict[str, Any],
    resolve: Callable[[str], Optional[Dict[str, Any]]],
    max_megas: int,
    lang: str = "es",
) -> Tuple[List[str], List[str]]:
    """Auditoría de SOLO LECTURA con las mismas reglas que el validador: devuelve (infracciones, recomendaciones)."""
    from src.core.era_rules import legal_abilities

    mech, fmt = pool["mechanics"], pool["format"]["name"]
    gen = int(mech.get("gen", 9) or 9)
    R = _rules(pool)
    legal, legal_items, lm = pool["legal_pokemon"], pool["legal_items"], pool["legal_moves"]
    champions = "champions" in nid(pool["format"].get("id", ""))
    errors: List[str] = []
    warnings: List[str] = []
    err = lambda key, **kw: errors.append(msg(key, lang, **kw))

    if len(team) != 6:
        warnings.append(msg("au_size", lang, n=len(team)))
    bases: Set[str] = set()
    used_items: Set[str] = set()
    megas = restricted = 0
    has_z = has_tera = False
    sleep_seen = False
    for slot in team:
        sp = slot.get("species", "?")
        e = resolve(sp)
        if not e:
            err("au_unknown", s=sp)
            continue
        if nid(e.get("id") or e["name"]) not in legal:
            err("au_species", s=sp, f=fmt)
        b = nid(e.get("baseSpecies") or e["name"])
        if b in bases:
            err("au_clause", s=sp)
        bases.add(b)
        megas += bool(e.get("is_mega"))
        restricted += bool(e.get("is_restricted"))

        # elementos que no existen en la generación del formato
        item = (slot.get("item") or "").strip()
        iid = nid(item)
        if gen < 3 and (slot.get("ability") or "").strip():
            err("au_no_ability", s=sp, g=gen)
        if gen < 3 and (slot.get("nature") or "").strip():
            err("au_no_nature", s=sp, g=gen)
        if gen == 1 and iid and iid not in ("ninguno", "none"):
            err("au_no_item", s=sp, g=gen)

        # objeto
        if gen > 1 and iid and iid not in ("ninguno", "none"):
            obj = legal_items.get(iid)
            if obj is None or (R["evasion"] and iid in EVASION_ITEMS):
                err("au_item", s=sp, a=item)
            else:
                has_z = has_z or bool(obj.get("isZ"))
                if obj.get("megaStone") and not e.get("is_mega") and nid(obj["megaStone"]) not in (nid(e["name"]), nid(sp)):
                    err("au_stone", s=sp, a=item)
                if R["item_clause"] and iid in used_items:
                    err("au_item_dup", s=sp, a=item)
            used_items.add(iid)
            req = e.get("requiredItem") if isinstance(e.get("requiredItem"), str) else None
            if req and iid != nid(req):
                err("au_item_forced", s=sp, a=item, b=req)
        elif e.get("is_mega") and gen > 1:
            req = e.get("requiredItem") if isinstance(e.get("requiredItem"), str) else None
            if req:
                err("au_item_forced", s=sp, a="-", b=req)

        # habilidad
        abil = (slot.get("ability") or "").strip()
        if gen >= 3 and abil:
            opts = {nid(a) for a in legal_abilities(e, gen)}
            if opts and nid(abil) not in opts:
                err("au_ability", s=sp, a=abil)
            elif nid(abil) in R["ban"] or (R["evasion_ab"] and nid(abil) in EVASION_ABILITIES):
                err("au_ability_ban", s=sp, a=abil)

        # movimientos
        moves = [m for m in (slot.get("moves") or []) if m]
        if len(moves) > 4:
            err("au_moves_n", s=sp, n=len(moves))
        learn = full_learnset(e)
        seen: Set[str] = set()
        for mv in moves:
            mid = nid(mv)
            if mid in seen:
                err("au_move_dup", s=sp, a=mv)
                continue
            seen.add(mid)
            if mid not in lm or mid in R["ban"] or (R["ohko"] and mid in OHKO) or (R["evasion"] and mid in EVASION_MOVES):
                err("au_move_ban", s=sp, a=mv)
            elif learn and mid not in learn:
                err("au_move_learn", s=sp, a=mv)
            if R["sleep"] and mid in SLEEP_MOVES:
                if sleep_seen:
                    err("au_sleep", s=sp, a=mv)
                sleep_seen = True

        # EVs / naturaleza / Tera
        if gen >= 3:
            evs = slot.get("evs") or {}
            if any(v > 252 for v in evs.values()):
                err("au_ev252", s=sp)
            elif champions and sum(_pts(v) for v in evs.values()) > 66:
                err("au_points", s=sp, n=sum(_pts(v) for v in evs.values()))
            elif not champions and sum(evs.values()) > 510:
                err("au_ev_total", s=sp, n=sum(evs.values()), m=510)
            nat = slot.get("nature")
            if nat and nid(nat) not in NATURES:
                err("au_nature", s=sp, a=nat)
        tt = slot.get("tera_type")
        if tt:
            has_tera = True
            if not mech.get("allow_tera"):
                err("au_tera", s=sp)
            elif tt not in TYPES:
                err("au_tera_type", s=sp, a=tt)

    if megas > max_megas:
        err("au_megas", n=megas, f=fmt, m=max_megas)
    if mech.get("max_restricted", 0) and restricted > mech["max_restricted"]:
        err("au_restricted", n=restricted, m=mech["max_restricted"])
    if mech.get("allow_megas") and megas == 0:
        warnings.append(msg("aw_mega", lang))
    if mech.get("allow_z_moves") and not has_z:
        warnings.append(msg("aw_z", lang))
    if mech.get("allow_tera") and not has_tera:
        warnings.append(msg("aw_tera", lang))
    if mech.get("allow_dynamax"):
        ents = [x for x in (resolve(t.get("species", "")) for t in team) if x]
        if ents:
            best = max(ents, key=lambda x: sum((x.get("baseStats") or {}).values()))
            warnings.append(msg("dyna_pick", lang, s=best["name"]))
    return errors, warnings
