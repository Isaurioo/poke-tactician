"""
Servicio del Compendio (Pokémon, movimientos, objetos y habilidades).

Lee los JSON de src/data/ una sola vez. Los archivos "extendidos" que genera
build_db_extended.py (learnsets.json, moves_full.json, pokedex_extra.json,
items_extra.json, descriptions_full.json) son OPCIONALES: si existen se fusionan
con los datos base y el compendio muestra más información; si no, funciona igual.
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.ability_categories import classify as classify_ability, is_placeholder, looks_english

logger = logging.getLogger("uvicorn")

# Cachés base (se rellenan IN PLACE para que quien las importe por referencia vea los datos).
_POKEDEX_CACHE: Dict[str, Any] = {}
_ITEMS_CACHE: Dict[str, Any] = {}
_MOVES_CACHE: Dict[str, Any] = {}
_ABILITIES_CACHE: Dict[str, Any] = {}
_DESCRIPTIONS_CACHE: Dict[str, Any] = {}

# Cachés opcionales (build_db_extended.py)
_LEARNSETS: Dict[str, Dict[str, List[str]]] = {}
_MOVES_FULL: Dict[str, Any] = {}
_POKE_EXTRA: Dict[str, Any] = {}
_ITEMS_EXTRA: Dict[str, Any] = {}
_DESC_FULL: Dict[str, Any] = {}
_I18N: Dict[str, Any] = {}   # i18n_data.json: nombres/descripciones es y fr

# Índices derivados
_NAME_TO_ID: Dict[str, str] = {}
_MOVE_LEARNERS: Dict[str, List[str]] = {}
_ABILITY_USERS: Dict[str, List[Dict[str, Any]]] = {}
_ITEM_REQUIRED_BY: Dict[str, List[str]] = {}
_FORMS_BY_BASE: Dict[str, List[str]] = {}
_FILES_LOADED = False

# Lista maestra de Ultra Entes (Respaldo infalible por si no hay tags en la DB)
_ULTRA_BEASTS = {
    "nihilego", "buzzwole", "pheromosa", "xurkitree", "celesteela", 
    "kartana", "guzzlord", "poipole", "naganadel", "stakataka", "blacephalon"
}

# Qué extras existen realmente (el frontend los usa para avisar de datos que faltan)
_CAPABILITIES: Dict[str, bool] = {}


def _nid(text: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _find_data_dir() -> Path:
    candidates = [
        Path("src/data"),
        Path("data"),
        Path(__file__).resolve().parent.parent / "data",
        Path(__file__).resolve().parent / "data",
    ]
    for c in candidates:
        if c.exists() and (c / "pokedex.json").exists():
            return c
    return Path("src/data")


def _replace(target: Dict[str, Any], new: Dict[str, Any]) -> None:
    target.clear()
    target.update(new)


def _load_compendium_files():
    global _FILES_LOADED
    if _FILES_LOADED:
        return

    data_dir = _find_data_dir()

    def _read_json(filename: str) -> Any:
        p = data_dir / filename
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando {filename}: {e}")
        return {}

    _replace(_POKEDEX_CACHE, _read_json("pokedex.json"))
    _replace(_ITEMS_CACHE, _read_json("items.json"))
    _replace(_MOVES_CACHE, _read_json("moves.json"))
    _replace(_ABILITIES_CACHE, _read_json("abilities.json"))

    desc_a = _read_json("showdown_descriptions.json")
    desc_b = _read_json("descriptions.json")
    merged = {}
    for section in ("moves", "items", "abilities"):
        merged[section] = {**(desc_a.get(section) or {}), **(desc_b.get(section) or {})}
    _replace(_DESCRIPTIONS_CACHE, merged)

    _replace(_LEARNSETS, _read_json("learnsets.json"))
    _replace(_MOVES_FULL, _read_json("moves_full.json"))
    _replace(_POKE_EXTRA, _read_json("pokedex_extra.json"))
    _replace(_ITEMS_EXTRA, _read_json("items_extra.json"))
    _replace(_DESC_FULL, _read_json("descriptions_full.json"))
    _replace(_I18N, _read_json("i18n_data.json"))

    _build_indexes()

    _CAPABILITIES.update({
        "learn_sources": bool(_LEARNSETS),
        "moves_full": bool(_MOVES_FULL),
        "pokedex_extra": bool(_POKE_EXTRA),
        "items_extra": bool(_ITEMS_EXTRA),
        "long_descriptions": bool(_DESC_FULL),
        "translations": bool(_I18N),
    })

    _FILES_LOADED = True
    logger.info(
        f"Compendio cargado: {len(_POKEDEX_CACHE)} Pokémon, {len(_MOVES_CACHE)} Movimientos, "
        f"{len(_ITEMS_CACHE)} Objetos, {len(_ABILITIES_CACHE)} Habilidades. Extras: {_CAPABILITIES}"
    )


def _build_indexes() -> None:
    _NAME_TO_ID.clear()
    _MOVE_LEARNERS.clear()
    _ABILITY_USERS.clear()
    _ITEM_REQUIRED_BY.clear()
    _FORMS_BY_BASE.clear()

    for pid, p in _POKEDEX_CACHE.items():
        _NAME_TO_ID[_nid(p.get("name", pid))] = pid

        for m_id in p.get("learnset", []):
            _MOVE_LEARNERS.setdefault(m_id, []).append(pid)

        for slot, ab_name in (p.get("abilities_map") or {}).items():
            _ABILITY_USERS.setdefault(_nid(ab_name), []).append(
                {"pid": pid, "slot": slot, "name": ab_name}
            )

        req = p.get("requiredItem")
        if req:
            _ITEM_REQUIRED_BY.setdefault(_nid(req), []).append(pid)

        _FORMS_BY_BASE.setdefault(_nid(p.get("baseSpecies", p.get("name"))), []).append(pid)


# ---------------------------------------------------------------------------
# Utilidades de normalización
# ---------------------------------------------------------------------------
def _resolve_pokemon_id(name: str) -> Optional[str]:
    clean = _nid(name)
    if clean in _POKEDEX_CACHE:
        return clean
    return _NAME_TO_ID.get(clean)


def _acc(value: Any) -> Optional[int]:
    if value is True or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bp(value: Any) -> Optional[int]:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _text(val: Any) -> str:
    if isinstance(val, dict):
        return val.get("desc") or val.get("shortDesc") or ""
    return val if isinstance(val, str) else ""


def _poke_summary(pid: str, extra: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    p = _POKEDEX_CACHE.get(pid)
    if not p:
        return None
    row = {
        "id": pid,
        "num": p.get("num", 0),
        "name": p.get("name", pid),
        "base_species": p.get("baseSpecies", p.get("name", pid)),
        "types": p.get("types", ["Normal"]),
        "bst": p.get("bst", 0),
        "tier": p.get("tier", "Unspecified"),
        "forme": p.get("forme", "Base"),
    }
    if extra:
        row.update(extra)
    return row


def _poke_list(pids: List[str], extras: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    rows = []
    for pid in dict.fromkeys(pids):
        r = _poke_summary(pid, (extras or {}).get(pid))
        if r:
            rows.append(r)
    rows.sort(key=lambda r: (r["num"], r["name"]))
    return rows


# ---------------------------------------------------------------------------
# Movimientos
# ---------------------------------------------------------------------------
_MOVE_PROPERTY_KEYS = [
    "drain", "recoil", "heal", "multihit", "multiaccuracy", "critRatio", "ohko", "willCrit",
    "selfSwitch", "forceSwitch", "boosts", "self", "status", "volatileStatus", "sideCondition",
    "slotCondition", "weather", "terrain", "pseudoWeather", "secondary", "secondaries",
    "zMove", "maxMove", "contestType", "isZ", "isMax", "overrideOffensiveStat",
    "overrideDefensiveStat", "overrideOffensivePokemon", "overrideDefensivePokemon",
    "ignoreDefensive", "ignoreEvasion", "ignoreImmunity", "ignoreAbility", "breaksProtect",
    "stallingMove", "noPPBoosts", "mindBlownRecoil", "struggleRecoil", "thawsTarget",
    "damage", "sleepUsable", "hasCrashDamage", "isFutureMove",
]


def _move_record(m_id: str) -> Optional[Dict[str, Any]]:
    base = _MOVES_CACHE.get(m_id)
    full = _MOVES_FULL.get(m_id)
    if not base and not full:
        return None
    return {**(base or {}), **(full or {})}


def _move_descriptions(m_id: str, rec: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    rec = rec or {}
    full = (_DESC_FULL.get("moves") or {}).get(m_id) or {}
    basic = (_DESCRIPTIONS_CACHE.get("moves") or {}).get(m_id) or {}
    short = full.get("shortDesc") or basic.get("shortDesc") or rec.get("shortDesc") or ""
    long_ = full.get("desc") or basic.get("desc") or rec.get("desc") or ""
    return {"short": short, "long": long_ if long_ != short else ""}


def get_move_detail(name: str) -> Optional[Dict[str, Any]]:
    _load_compendium_files()
    m_id = _nid(name)
    if m_id not in _MOVES_CACHE and m_id not in _MOVES_FULL:
        found = next((k for k, v in _MOVES_CACHE.items() if _nid(v.get("name")) == m_id), None)
        if not found:
            return None
        m_id = found

    rec = _move_record(m_id) or {}
    descs = _move_descriptions(m_id, rec)
    props = {k: rec[k] for k in _MOVE_PROPERTY_KEYS if k in rec and rec[k] not in (None, False)}

    learner_ids = list(_MOVE_LEARNERS.get(m_id, []))
    if _LEARNSETS:
        for pid in _POKEDEX_CACHE:
            if m_id in _move_sources(pid):
                learner_ids.append(pid)

    sources_by_poke: Dict[str, Dict[str, Any]] = {}
    if _LEARNSETS:
        for pid in set(learner_ids):
            src = _move_sources(pid).get(m_id)
            if src:
                sources_by_poke[pid] = {"sources": src["codes"], "via": src["via"]}

    return {
        "id": m_id,
        "num": rec.get("num"),
        "name": rec.get("name", m_id),
        "type": rec.get("type", "Normal"),
        "category": rec.get("category", "Status"),
        "base_power": _bp(rec.get("basePower")),
        "accuracy": _acc(rec.get("accuracy")),
        "never_misses": rec.get("accuracy") is True,
        "pp": rec.get("pp"),
        "priority": rec.get("priority", 0),
        "target": rec.get("target"),
        "flags": sorted((rec.get("flags") or {}).keys()) if isinstance(rec.get("flags"), dict) else (rec.get("flags") or []),
        "short_desc": descs["short"],
        "desc": descs["long"],
        "is_past": bool(rec.get("isPast") or rec.get("isNonstandard") == "Past"),
        "properties": props,
        "has_extended_data": bool(_MOVES_FULL.get(m_id)),
        "learners": _poke_list(learner_ids, sources_by_poke),
    }


# ---------------------------------------------------------------------------
# Habilidades
# ---------------------------------------------------------------------------
def _ability_record(ab_name: str) -> Dict[str, Any]:
    ab_id = _nid(ab_name)
    rec = _ABILITIES_CACHE.get(ab_id)
    if isinstance(rec, dict):
        return rec
    for v in _ABILITIES_CACHE.values():
        if isinstance(v, dict) and _nid(v.get("name")) == ab_id:
            return v
    return {}


def _ability_texts(ab_name: str) -> Dict[str, Any]:
    ab_id = _nid(ab_name)
    rec = _ability_record(ab_name)
    full_en = (_DESC_FULL.get("abilities") or {}).get(ab_id) or {}
    basic = (_DESCRIPTIONS_CACHE.get("abilities") or {}).get(ab_id)

    es = rec.get("desc") or rec.get("shortDesc") or ""
    es_short = rec.get("shortDesc") or ""
    en = full_en.get("desc") or _text(basic) or ""
    en_short = full_en.get("shortDesc") or ""

    if is_placeholder(es):
        es = ""
    if is_placeholder(es_short):
        es_short = ""
    if es and looks_english(es):
        en = en or es
        es = ""
    if es_short and looks_english(es_short):
        en_short = en_short or es_short
        es_short = ""

    category, tags = classify_ability(es, en or en_short, ab_id)
    return {
        "es": es,
        "es_short": es_short,
        "en": en,
        "en_short": en_short,
        "name_es": rec.get("name_es") or "",
        "category": category,
        "tags": tags,
        "no_desc": not (es or en or en_short),
    }


def _get_ability_description(ability_name: str) -> str:
    t = _ability_texts(ability_name)
    return t["es"] or t["en"] or t["en_short"] or ""


def get_ability_detail(name: str) -> Optional[Dict[str, Any]]:
    _load_compendium_files()
    ab_id = _nid(name)
    users = _ABILITY_USERS.get(ab_id, [])
    rec = _ability_record(name)
    if not rec and not users:
        return None
    display_name = rec.get("name") or (users[0]["name"] if users else name)
    t = _ability_texts(display_name)

    slot_info = {u["pid"]: {"slot": u["slot"], "hidden": u["slot"] == "H"} for u in users}
    return {
        "id": ab_id,
        "name": display_name,
        "name_es": t["name_es"],
        "desc": t["es"],
        "short_desc": t["es_short"],
        "desc_en": t["en"] or t["en_short"],
        "short_desc_en": t["en_short"],
        "category": t["category"],
        "tags": t["tags"],
        "no_desc": t["no_desc"],
        "pokemon": _poke_list([u["pid"] for u in users], slot_info),
    }


# ---------------------------------------------------------------------------
# Objetos
# ---------------------------------------------------------------------------
def _item_category(it: Dict[str, Any]) -> str:
    name = it.get("name", "")
    it_id = it.get("id", _nid(name))
    
    comp_ids = {
        "assaultvest", "rockyhelmet", "focussash", "leftovers", "eviolite",
        "heavydutyboots", "clearamulet", "covertcloak", "loadeddice",
        "safetygoggles", "lightclay", "kingsrock", "weaknesspolicy", "blunderpolicy",
        "roomservice", "airballoon", "ejectbutton", "ejectpack", "redcard",
        "terrainextender", "damprock", "heatrock", "smoothrock", "icyrock",
        "toxicorb", "flameorb"
    }
    
    dmg_ids = {
        "lifeorb", "expertbelt", "muscleband", "wiseglasses", "punchingglove",
        "mysticwater", "charcoal", "magnet", "miracleseed", "nevermeltice",
        "dragonfang", "hardstone", "poisonbarb", "silverpowder", "softsand",
        "sharpbeak", "metalcoat", "twistedspoon", "fairyfeather", "blackbelt",
        "silkscarf", "blackglasses", "spelltag", "choiceband", "choicespecs"
    }
    
    required_by = _ITEM_REQUIRED_BY.get(it_id, [])
    if it.get("megaStone") or any(_POKEDEX_CACHE[p].get("is_mega") for p in required_by):
        return "megastone"
    if re.search(r"ium Z$", name) or it.get("zMove"):
        return "zcrystal"
        
    if it_id in comp_ids:
        return "competitive"
        
    if it.get("isChoice") or name.startswith("Choice "):
        return "choice"
        
    if it_id in dmg_ids:
        return "damage"

    if name.endswith(" Berry") or it.get("isBerry"):
        return "berry"
    if name.endswith(" Plate") or it.get("onPlate"):
        return "plate"
    if name.endswith(" Memory") or it.get("onMemory"):
        return "memory"
    if name.endswith(" Drive") or it.get("onDrive"):
        return "drive"
    if name.endswith(" Gem") or it.get("isGem"):
        return "gem"
    if name.endswith(" Ball") or it.get("isPokeball"):
        return "pokeball"
    if name.endswith(" Mask"):
        return "mask"
    if name.endswith(" Seed"):
        return "seed"
    if name.endswith(" Fossil"):
        return "fossil"
    if name.endswith(" Mail"):
        return "mail"
    if name.endswith(" Herb"):
        return "herb"
    if name.endswith(" Orb") or name.endswith(" Crystal"):
        return "orb"
        
    return "general"


def _item_description(it_id: str, it: Dict[str, Any]) -> Dict[str, str]:
    full = (_DESC_FULL.get("items") or {}).get(it_id) or {}
    basic = (_DESCRIPTIONS_CACHE.get("items") or {}).get(it_id)
    basic_txt = _text(basic)
    short = full.get("shortDesc") or basic_txt or it.get("desc") or ""
    long_ = full.get("desc") or ""
    derived = ""
    if not short:
        required_by = _ITEM_REQUIRED_BY.get(it_id, [])
        megas = [_POKEDEX_CACHE[p]["name"] for p in required_by if _POKEDEX_CACHE[p].get("is_mega")]
        if megas:
            holder = _POKEDEX_CACHE[required_by[0]].get("baseSpecies", "")
            derived = f"Permite a {holder} megaevolucionar a {', '.join(megas)}."
        elif required_by:
            derived = f"Objeto requerido por {', '.join(_POKEDEX_CACHE[p]['name'] for p in required_by[:4])}."
    return {"short": short or derived, "long": long_ if long_ != short else "", "derived": bool(derived and not short)}


def get_item_detail(name: str) -> Optional[Dict[str, Any]]:
    _load_compendium_files()
    it_id = _nid(name)
    it = _ITEMS_CACHE.get(it_id)
    if not it:
        it = next((v for v in _ITEMS_CACHE.values() if _nid(v.get("name")) == it_id), None)
        if not it:
            return None
        it_id = it.get("id", it_id)

    extra = _ITEMS_EXTRA.get(it_id, {})
    rec = {**it, **extra}
    d = _item_description(it_id, rec)

    user_ids = [_resolve_pokemon_id(u) for u in rec.get("itemUser", []) or []]
    required_ids = list(_ITEM_REQUIRED_BY.get(it_id, []))

    props = {k: rec[k] for k in ("fling", "naturalGift", "boosts", "zMove", "zMoveType", "zMoveFrom",
                                 "forcedForme", "onPlate", "onMemory", "onDrive") if k in rec}
    return {
        "id": it_id,
        "num": rec.get("num"),
        "gen": rec.get("gen"),
        "spritenum": rec.get("spritenum"),
        "name": it["name"],
        "category": _item_category(rec),
        "short_desc": d["short"],
        "desc": d["long"],
        "desc_is_derived": d["derived"],
        "is_past": bool(rec.get("isPast") or rec.get("isNonstandard") == "Past"),
        "is_choice": bool(rec.get("isChoice")),
        "mega_evolves": rec.get("megaEvolves"),
        "mega_stone": rec.get("megaStone"),
        "properties": props,
        "users": _poke_list([u for u in user_ids if u]),
        "required_by": _poke_list(required_ids),
    }


# ---------------------------------------------------------------------------
# Pokémon
# ---------------------------------------------------------------------------
def _own_sources(pid: str) -> Dict[str, List[str]]:
    p = _POKEDEX_CACHE.get(pid, {})
    base_id = _nid(p.get("baseSpecies", p.get("name")))
    return _LEARNSETS.get(pid) or _LEARNSETS.get(base_id) or {}


def _move_sources(pid: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for mv, codes in _own_sources(pid).items():
        out[mv] = {"codes": list(codes), "via": None}

    seen = {pid}
    current = pid
    while True:
        prevo_name = (_POKE_EXTRA.get(current) or {}).get("prevo")
        prevo_id = _resolve_pokemon_id(prevo_name) if prevo_name else None
        if not prevo_id or prevo_id in seen:
            break
        seen.add(prevo_id)
        prevo_display = _POKEDEX_CACHE.get(prevo_id, {}).get("name", prevo_name)
        for mv, codes in _own_sources(prevo_id).items():
            if mv not in out:
                out[mv] = {"codes": list(codes), "via": prevo_display}
        current = prevo_id
    return out


def _evolution_tree(pid: str) -> Optional[Dict[str, Any]]:
    if not _POKE_EXTRA:
        return None

    root = pid
    seen = {root}
    while True:
        prevo_name = (_POKE_EXTRA.get(root) or {}).get("prevo")
        prevo_id = _resolve_pokemon_id(prevo_name) if prevo_name else None
        if not prevo_id or prevo_id in seen:
            break
        seen.add(prevo_id)
        root = prevo_id

    def node(cur: str, depth: int = 0) -> Dict[str, Any]:
        ex = _POKE_EXTRA.get(cur, {})
        p = _POKEDEX_CACHE.get(cur, {})
        n: Dict[str, Any] = {
            "id": cur,
            "name": p.get("name", cur),
            "base_species": p.get("baseSpecies", p.get("name", cur)),
            "forme": p.get("forme", "Base"),
            "types": p.get("types", []),
            "how": None,
            "children": [],
        }
        if ex.get("prevo"):
            n["how"] = {k: ex[k] for k in ("evoLevel", "evoType", "evoItem", "evoCondition", "evoMove") if k in ex}
        if depth < 4:
            for evo_name in ex.get("evos", []) or []:
                evo_id = _resolve_pokemon_id(evo_name)
                if evo_id and evo_id != cur:
                    n["children"].append(node(evo_id, depth + 1))
        return n

    tree = node(root)
    return tree if tree["children"] or root != pid else None


def get_pokemon_detail(name: str) -> Optional[Dict[str, Any]]:
    _load_compendium_files()
    pid = _resolve_pokemon_id(name)
    if not pid:
        return None
    poke = _POKEDEX_CACHE[pid]
    extra = _POKE_EXTRA.get(pid, {})
    base_key = _nid(poke.get("baseSpecies", poke.get("name")))

    abilities = []
    amap = poke.get("abilities_map") or {str(i): a for i, a in enumerate(poke.get("abilities", []))}
    slot_labels = {"0": "Habilidad 1", "1": "Habilidad 2", "H": "Habilidad oculta", "S": "Habilidad especial"}
    for slot, ab in amap.items():
        t = _ability_texts(ab)
        abilities.append({
            "id": _nid(ab),
            "name": ab,
            "name_es": t["name_es"],
            "slot": slot,
            "slot_label": slot_labels.get(slot, f"Habilidad {slot}"),
            "hidden": slot == "H",
            "desc": t["es"] or t["en"] or t["en_short"],
            "desc_es": t["es"],
            "desc_en": t["en"] or t["en_short"],
            "category": t["category"],
        })

    sources = _move_sources(pid) if _LEARNSETS else {}
    move_ids = list(sources.keys()) if sources else list(poke.get("learnset", []))
    moves = []
    for m_id in move_ids:
        rec = _move_record(m_id)
        if not rec:
            continue
        descs = _move_descriptions(m_id, rec)
        src = sources.get(m_id)
        moves.append({
            "id": m_id,
            "name": rec.get("name", m_id),
            "type": rec.get("type", "Normal"),
            "category": rec.get("category", "Status"),
            "base_power": _bp(rec.get("basePower")),
            "accuracy": _acc(rec.get("accuracy")),
            "pp": rec.get("pp"),
            "priority": rec.get("priority", 0),
            "target": rec.get("target"),
            "short_desc": descs["short"],
            "is_past": bool(rec.get("isPast") or rec.get("isNonstandard") == "Past"),
            "sources": src["codes"] if src else [],
            "via": src["via"] if src else None,
        })
    moves.sort(key=lambda x: x["name"])

    forms = _poke_list([f for f in _FORMS_BY_BASE.get(base_key, []) if f != pid])

    flags = {k: bool(poke.get(k)) for k in ("is_mega", "is_primal", "is_restricted", "is_sublegend", "is_paradox", "is_mythical")}
    # Integración del validador de Ultra Entes
    flags["is_ultrabeast"] = (
        "Ultra Beast" in poke.get("tags", []) 
        or "Ultra Beast" in extra.get("tags", []) 
        or base_key in _ULTRA_BEASTS
    )

    extra_out = {k: v for k, v in extra.items() if k not in ("evos", "prevo", "evoLevel", "evoType", "evoItem", "evoCondition", "evoMove")}

    return {
        "id": pid,
        "num": poke.get("num", 0),
        "name": poke.get("name", name),
        "base_species": poke.get("baseSpecies", poke.get("name")),
        "forme": poke.get("forme", "Base"),
        "types": poke.get("types", ["Normal"]),
        "base_stats": poke.get("baseStats", {}),
        "bst": poke.get("bst", 0),
        "tier": poke.get("tier", "Unspecified"),
        "doubles_tier": poke.get("doublesTier", "Unspecified"),
        "natdex_tier": poke.get("natDexTier", "Unspecified"),
        "required_item": poke.get("requiredItem"),
        "flags": flags,
        "abilities": [a["name"] for a in abilities],
        "ability_details": abilities,
        "extra": extra_out,
        "evolution": _evolution_tree(pid),
        "forms": forms,
        "learnable_moves": moves,
        "has_learn_sources": bool(sources),
    }


# ---------------------------------------------------------------------------
# Resumen para el listado general
# ---------------------------------------------------------------------------
def get_species_types(species_name: str) -> List[str]:
    _load_compendium_files()
    clean = _nid(species_name)

    if clean in _POKEDEX_CACHE:
        return _POKEDEX_CACHE[clean].get("types", ["Normal"])

    for p in _POKEDEX_CACHE.values():
        if _nid(p.get("name", "")) == clean:
            return p.get("types", ["Normal"])

    if "charizardmegax" in clean:
        return ["Fire", "Dragon"]
    if "charizardmegay" in clean:
        return ["Fire", "Flying"]
    if "sceptilemega" in clean:
        return ["Grass", "Dragon"]
    if "gyaradosmega" in clean:
        return ["Water", "Dark"]
    if "ampharosmega" in clean:
        return ["Electric", "Dragon"]
    if "aggronmega" in clean:
        return ["Steel"]
    if "lopunnymega" in clean:
        return ["Normal", "Fighting"]

    base_clean = re.sub(r"(mega[xy]?|gmax|alola|galar|hisui|paldea).*", "", clean)
    if base_clean and base_clean in _POKEDEX_CACHE:
        return _POKEDEX_CACHE[base_clean].get("types", ["Normal"])

    return ["Normal"]


def get_compendium_overview() -> Dict[str, Any]:
    _load_compendium_files()

    pokemon_list = []
    ability_count: Dict[str, int] = {}
    for pid, p in _POKEDEX_CACHE.items():
        if p.get("num", 0) <= 0:
            continue
        for ab in p.get("abilities", []):
            ability_count[_nid(ab)] = ability_count.get(_nid(ab), 0) + 1
            
        extra = _POKE_EXTRA.get(pid, {})
        base_species_id = _nid(p.get("baseSpecies", p.get("name", "")))
        is_ub = (
            "Ultra Beast" in p.get("tags", []) 
            or "Ultra Beast" in extra.get("tags", []) 
            or base_species_id in _ULTRA_BEASTS
        )

        pokemon_list.append({
            "id": pid,
            "num": p["num"],
            "name": p["name"],
            "base_species": p.get("baseSpecies", p["name"]),
            "forme": p.get("forme", "Base"),
            "types": p["types"],
            "base_stats": p.get("baseStats", {}),
            "bst": p.get("bst", 0),
            "abilities": p.get("abilities", []),
            "tier": p.get("tier", "Unspecified"),
            "doubles_tier": p.get("doublesTier", "Unspecified"),
            "is_mega": p.get("is_mega", False),
            "is_primal": p.get("is_primal", False),
            "is_restricted": p.get("is_restricted", False),
            "is_sublegend": p.get("is_sublegend", False),
            "is_paradox": p.get("is_paradox", False),
            "is_mythical": p.get("is_mythical", False),
            "is_ultrabeast": is_ub,
            "moves_count": len(p.get("learnset", [])),
        })
    pokemon_list.sort(key=lambda x: (x["num"], x["name"]))

    items_list = []
    for it_id, it in _ITEMS_CACHE.items():
        rec = {**it, **_ITEMS_EXTRA.get(it_id, {})}
        d = _item_description(it_id, rec)
        items_list.append({
            "id": it_id,
            "name": it["name"],
            "spritenum": rec.get("spritenum"),
            "desc": d["short"],
            "category": _item_category(rec),
            "is_past": bool(rec.get("isPast") or rec.get("isNonstandard") == "Past"),
            "has_desc": bool(d["short"]),
        })
    items_list.sort(key=lambda x: x["name"])

    moves_list = []
    for m_id in list(_MOVES_CACHE.keys()):
        rec = _move_record(m_id) or {}
        descs = _move_descriptions(m_id, rec)
        flags = rec.get("flags")
        moves_list.append({
            "id": m_id,
            "name": rec.get("name", m_id),
            "type": rec.get("type", "Normal"),
            "category": rec.get("category", "Status"),
            "base_power": _bp(rec.get("basePower")),
            "accuracy": _acc(rec.get("accuracy")),
            "pp": rec.get("pp"),
            "priority": rec.get("priority", 0),
            "target": rec.get("target"),
            "flags": sorted(flags.keys()) if isinstance(flags, dict) else (flags or []),
            "desc": descs["short"],
            "is_past": bool(rec.get("isPast") or rec.get("isNonstandard") == "Past"),
            "learners_count": len(_MOVE_LEARNERS.get(m_id, [])),
        })
    moves_list.sort(key=lambda x: x["name"])

    abilities_list = []
    seen = set()
    for ab_id, rec in _ABILITIES_CACHE.items():
        if not isinstance(rec, dict):
            continue
        seen.add(ab_id)
        t = _ability_texts(rec.get("name", ab_id))
        abilities_list.append({
            "id": ab_id,
            "name": rec.get("name", ab_id),
            "name_es": rec.get("name_es", ""),
            "desc": t["es"] or t["en"] or t["en_short"],
            "desc_es": t["es"],
            "desc_en": t["en"] or t["en_short"],
            "category": t["category"],
            "tags": t["tags"],
            "no_desc": t["no_desc"],
            "pokemon_count": ability_count.get(ab_id, 0),
        })
    for ab_id, users in _ABILITY_USERS.items():
        if ab_id in seen:
            continue
        name = users[0]["name"]
        t = _ability_texts(name)
        abilities_list.append({
            "id": ab_id,
            "name": name,
            "name_es": "",
            "desc": t["es"] or t["en"] or t["en_short"],
            "desc_es": t["es"],
            "desc_en": t["en"] or t["en_short"],
            "category": t["category"],
            "tags": t["tags"],
            "no_desc": t["no_desc"],
            "pokemon_count": ability_count.get(ab_id, 0),
        })
    abilities_list.sort(key=lambda x: x["name"])

    return {
        "stats": {
            "total_pokemon": len(pokemon_list),
            "total_items": len(items_list),
            "total_moves": len(moves_list),
            "total_abilities": len(abilities_list),
        },
        "capabilities": dict(_CAPABILITIES),
        "pokemon": pokemon_list,
        "items": items_list,
        "moves": moves_list,
        "abilities": abilities_list,
    }


def get_item_icon_map() -> Dict[str, int]:
    _load_compendium_files()
    out: Dict[str, int] = {}
    for it_id in _ITEMS_CACHE:
        sn = (_ITEMS_EXTRA.get(it_id) or {}).get("spritenum")
        if sn is None:
            sn = _ITEMS_CACHE[it_id].get("spritenum")
        if isinstance(sn, int):
            out[it_id] = sn
    return out


def describe_terms(abilities: List[str], items: List[str], moves: List[str]) -> Dict[str, Dict[str, str]]:
    _load_compendium_files()
    out: Dict[str, Dict[str, str]] = {"abilities": {}, "items": {}, "moves": {}}

    for name in dict.fromkeys(abilities or []):
        t = _ability_texts(name)
        text = t["en"] or t["en_short"]
        if text:
            out["abilities"][name] = text

    for name in dict.fromkeys(items or []):
        it_id = _nid(name)
        it = _ITEMS_CACHE.get(it_id)
        if it:
            d = _item_description(it_id, {**it, **_ITEMS_EXTRA.get(it_id, {})})
            if d["short"] and not d["derived"]:
                out["items"][name] = d["short"]

    for name in dict.fromkeys(moves or []):
        m_id = _nid(name)
        rec = _move_record(m_id)
        if rec:
            text = _move_descriptions(m_id, rec)["short"]
            if text:
                out["moves"][name] = text
    return out


# ---------------------------------------------------------------------------
# Traducciones (español / francés)
# ---------------------------------------------------------------------------
_FORME_TOKENS = {
    "Mega": {"fr": "Méga"},
    "Primal": {"es": "Primigenio", "fr": "Primo"},
    "Gmax": {"es": "Gigamax", "fr": "Gigamax"},
}


def _translated_pokemon_name(p: Dict[str, Any], lang: str) -> Optional[str]:
    tr = ((_I18N.get("pokemon") or {}).get(str(p.get("num", 0))) or {}).get(lang)
    if not tr:
        return None
    base = p.get("baseSpecies") or p.get("name") or ""
    name = p.get("name", "")
    suffix = name[len(base):] if base and name.startswith(base) else ""
    if suffix:
        suffix = "-".join(_FORME_TOKENS.get(x, {}).get(lang, x) for x in suffix.split("-"))
    return tr + suffix


def get_l10n(lang: str) -> Dict[str, Any]:
    _load_compendium_files()
    lang = (lang or "en").lower()[:2]
    out: Dict[str, Any] = {"lang": lang, "pokemon": {}, "moves": {}, "items": {}, "abilities": {}}
    if lang not in ("es", "fr"):
        return out

    for pid, p in _POKEDEX_CACHE.items():
        n = _translated_pokemon_name(p, lang)
        if n and n != p.get("name"):
            out["pokemon"][pid] = n

    for names_key, desc_key, ids in (
        ("moves", "move_desc", _MOVES_CACHE.keys()),
        ("items", "item_desc", _ITEMS_CACHE.keys()),
    ):
        names, descs = _I18N.get(names_key) or {}, _I18N.get(desc_key) or {}
        for i in ids:
            n = (names.get(i) or {}).get(lang) or ""
            d = (descs.get(i) or {}).get(lang) or ""
            if n or d:
                out[names_key][i] = [n, d]

    names, descs = _I18N.get("abilities") or {}, _I18N.get("ability_desc") or {}
    for ab_id in set(_ABILITIES_CACHE.keys()) | set(_ABILITY_USERS.keys()):
        rec = _ABILITIES_CACHE.get(ab_id) if isinstance(_ABILITIES_CACHE.get(ab_id), dict) else {}
        users = _ABILITY_USERS.get(ab_id, [])
        display = rec.get("name") or (users[0]["name"] if users else ab_id)
        n = (names.get(ab_id) or {}).get(lang) or (rec.get("name_es", "") if lang == "es" else "")
        d = (descs.get(ab_id) or {}).get(lang) or (_ability_texts(display)["es"] if lang == "es" else "")
        if n or d:
            out["abilities"][ab_id] = [n, d]
    return out