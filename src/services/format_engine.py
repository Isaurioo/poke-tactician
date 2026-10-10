"""
Motor Filtrador Estricto por Formato y Generación (Gen 1 a Gen 9 + Champions).
Garantiza que al elegir cualquier generación solo estén disponibles los Pokémon,
formas regionales, objetos, movimientos y mecánicas que existían en esa época.
Incluye soporte avanzado para 'whitelist' (Listas Blancas) en regulaciones cerradas.
"""
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Set, Tuple
import httpx

from src.services.smogon import fetch_live_format_chaos, normalize_id

logger = logging.getLogger("uvicorn")
DATA_DIR = Path("src/data")

POKEDEX_DB: Dict[str, Any] = {}
ITEMS_DB: Dict[str, Any] = {}
MOVES_DB: Dict[str, Any] = {}
FORMATS_DB: Dict[str, Any] = {}
CHAMPIONS_LEGAL_CACHE: Set[str] = set()

CHAMPIONS_FORMATS_DATA_URL = (
    "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/mods/champions/formats-data.ts"
)

# Límite oficial de la Pokédex Nacional por Generación
MAX_DEX_BY_GEN: Dict[int, int] = {
    1: 151, 2: 251, 3: 386, 4: 493, 5: 649, 6: 721, 7: 809, 8: 905, 9: 9999,
}

# Jerarquía estricta de Tiers para exclusión en cascada
SINGLES_TIER_ORDER = [
    "ag", "uber", "(uber)", "ou", "(ou)", "uubl", "uu", "rubl", "ru",
    "nubl", "nu", "(nu)", "publ", "pu", "(pu)", "zubl", "zu", "nfe", "lc"
]

DOUBLES_TIER_ORDER = [
    "duber", "(duber)", "dou", "(dou)", "dbl", "duu", "(duu)", "dnfe", "dlc"
]

# Especies canónicas de Pokémon restringidos / legendarios mayores
RESTRICTED_SPECIES: Set[str] = {
    "mewtwo", "lugia", "hooh", "kyogre", "groudon", "rayquaza",
    "dialga", "palkia", "giratina", "reshiram", "zekrom", "kyurem",
    "xerneas", "yveltal", "zygarde", "cosmog", "cosmoem", "solgaleo",
    "lunala", "necrozma", "zacian", "zamazenta", "eternatus",
    "calyrex", "koraidon", "miraidon", "terapagos"
}

# Especies insignia de Doubles OU / OU histórico que deben excluirse en tiers UU / DUU
DOUBLES_OU_STAPLES: Set[str] = {
    "tapukoko", "tapulele", "tapufini", "tapubulu", "kartana", "celesteela",
    "landorus", "landorustherian", "incineroar", "heatran", "zapdos", "amoonguss",
    "volcarona", "tyranitar", "salamence", "metagross", "kangaskhan", "charizard",
    "aegislash", "excadrill", "kommoo", "kyuremblack", "marshadow", "deoxys",
    "stakataka", "naganadel", "buzzwole", "pheromosa", "greninja", "ashgreninja",
    "hoopa", "hoopaunbound", "thundurus", "thundurustherian", "tornadus", "tornadustherian"
}

def load_local_databases():
    global POKEDEX_DB, ITEMS_DB, MOVES_DB, FORMATS_DB
    if not POKEDEX_DB and (DATA_DIR / "pokedex.json").exists():
        with open(DATA_DIR / "pokedex.json", "r", encoding="utf-8") as f:
            POKEDEX_DB = json.load(f)
    if not ITEMS_DB and (DATA_DIR / "items.json").exists():
        with open(DATA_DIR / "items.json", "r", encoding="utf-8") as f:
            ITEMS_DB = json.load(f)
        # items.json trae megaStone vacío: los datos reales de las Megapiedras están en items_extra.json
        extra_path = DATA_DIR / "items_extra.json"
        if extra_path.exists():
            with open(extra_path, "r", encoding="utf-8") as f:
                for iid, ex in json.load(f).items():
                    if iid in ITEMS_DB and ex.get("zMove"):
                        ITEMS_DB[iid]["isZ"] = True
                        if ex.get("zMoveType"):
                            ITEMS_DB[iid]["zMoveType"] = ex["zMoveType"]
                    ms = ex.get("megaStone")
                    if iid in ITEMS_DB and isinstance(ms, dict) and ms:
                        ITEMS_DB[iid]["megaEvolves"], ITEMS_DB[iid]["megaStone"] = next(iter(ms.items()))
    if not MOVES_DB and (DATA_DIR / "moves.json").exists():
        with open(DATA_DIR / "moves.json", "r", encoding="utf-8") as f:
            MOVES_DB = json.load(f)
    if not FORMATS_DB and (DATA_DIR / "formats.json").exists():
        with open(DATA_DIR / "formats.json", "r", encoding="utf-8") as f:
            FORMATS_DB = json.load(f)

async def get_champions_legal_pokemon() -> Set[str]:
    global CHAMPIONS_LEGAL_CACHE
    if CHAMPIONS_LEGAL_CACHE:
        return CHAMPIONS_LEGAL_CACHE

    cache_file = DATA_DIR / "champions_legal_strict.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                CHAMPIONS_LEGAL_CACHE = set(json.load(f))
                return CHAMPIONS_LEGAL_CACHE
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(CHAMPIONS_FORMATS_DATA_URL)
            if resp.status_code == 200:
                blocks = re.findall(r'([a-z0-9]+):\s*\{([^}]*)\}', resp.text)
                legal_ids = set()
                for poke_id, body in blocks:
                    if 'tier: "Illegal"' in body or 'isNonstandard: "Past"' in body or 'isNonstandard: "Future"' in body:
                        continue
                    if "tier:" in body or "doublesTier:" in body:
                        legal_ids.add(poke_id)

                if legal_ids:
                    CHAMPIONS_LEGAL_CACHE = legal_ids
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(sorted(list(legal_ids)), f, indent=2)
                    logger.info(f"==> Lista estricta de Champions cargada ({len(legal_ids)} entradas exactas).")
                    return CHAMPIONS_LEGAL_CACHE
    except Exception as e:
        logger.warning(f"No se pudo descargar formats-data de Champions: {e}")

    return set()

def get_official_formats_list() -> List[Dict[str, Any]]:
    load_local_databases()
    results = []
    for fmt_id, fmt in FORMATS_DB.items():
        results.append({
            "id": fmt_id,
            "name": fmt["name"],
            "game_type": fmt["game_type"],
            "mechanics": fmt.get("mechanics", {}),
        })
    return results

def is_forme_valid_in_gen(poke_entry: Dict[str, Any], gen_num: int, is_champions: bool) -> bool:
    forme = (poke_entry.get("forme") or "").lower()
    if not forme or forme == "base":
        return True
    if "paldea" in forme and gen_num < 9: return False
    if ("galar" in forme or "hisui" in forme) and gen_num < 8: return False
    if "alola" in forme and gen_num < 7: return False
    return True

def get_tier_banlist_for_format(clean_fmt: str, is_doubles: bool) -> Tuple[Set[str], Set[str]]:
    singles_banned: Set[str] = set()
    doubles_banned: Set[str] = set()
    is_ubers = "ubers" in clean_fmt or "anythinggoes" in clean_fmt

    if is_doubles:
        if "doublesuu" in clean_fmt or "duu" in clean_fmt:
            doubles_banned = {"duber", "(duber)", "dou", "(dou)", "dbl"}
            singles_banned = {"ag", "uber", "(uber)", "ou", "(ou)", "uubl"}
        elif ("doublesou" in clean_fmt or "dou" in clean_fmt) and not is_ubers:
            doubles_banned = {"duber", "(duber)"}
            singles_banned = {"ag", "uber", "(uber)"}
    else:
        if is_ubers:
            singles_banned = set()
        elif "uu" in clean_fmt and "ru" not in clean_fmt and "nu" not in clean_fmt:
            singles_banned = {"ag", "uber", "(uber)", "ou", "(ou)", "uubl"}
        elif "ru" in clean_fmt:
            singles_banned = {"ag", "uber", "(uber)", "ou", "(ou)", "uubl", "uu", "rubl"}
        elif "nu" in clean_fmt:
            singles_banned = {"ag", "uber", "(uber)", "ou", "(ou)", "uubl", "uu", "rubl", "ru", "nubl"}
        elif "pu" in clean_fmt:
            singles_banned = {"ag", "uber", "(uber)", "ou", "(ou)", "uubl", "uu", "rubl", "ru", "nubl", "publ"}
        elif "lc" in clean_fmt:
            singles_banned = {"ag", "uber", "(uber)", "ou", "(ou)", "uubl", "uu", "rubl", "ru", "nubl", "publ", "nfe"}
        elif "ou" in clean_fmt:
            singles_banned = {"ag", "uber", "(uber)"}
    return singles_banned, doubles_banned

async def filter_available_pool_for_format(format_id: str) -> Dict[str, Any]:
    load_local_databases()
    clean_fmt = normalize_id(format_id)

    gen_match = re.match(r"^gen([1-9])", clean_fmt)
    gen_num = int(gen_match.group(1)) if gen_match else 9
    max_dex_num = MAX_DEX_BY_GEN.get(gen_num, 9999)

    is_champions = "champion" in clean_fmt
    is_natdex = "nationaldex" in clean_fmt
    is_doubles = any(k in clean_fmt for k in ["vgc", "doubles", "bss"])

    fmt_info = FORMATS_DB.get(clean_fmt, {
        "id": clean_fmt,
        "name": format_id,
        "game_type": "doubles" if is_doubles else "singles",
        "mechanics": {"tera": False, "mega": False},
        "ruleset": [],
        "banlist": [],
    })

    allow_megas = fmt_info["mechanics"].get("mega", False)
    allow_tera = fmt_info["mechanics"].get("tera", False)

    ruleset_str = " ".join(fmt_info.get("ruleset", [])).lower()
    # formats.json solo trae mega/tera: Z y Dynamax se derivan de la generación y las cláusulas
    allow_z_moves = gen_num == 7 and "z-move clause" not in ruleset_str
    allow_dynamax = (gen_num == 8 and "dynamax clause" not in ruleset_str
                     and ("flat rules" in ruleset_str or "standard" in ruleset_str))
    banlist_set = {normalize_id(b) for b in fmt_info.get("banlist", [])}
    
    # LA MAGIA DE LA LISTA BLANCA (WHITELIST)
    whitelist_raw = fmt_info.get("whitelist", [])
    whitelist_set = {normalize_id(p) for p in whitelist_raw}

    is_reg_h = "regh" in clean_fmt
    is_reg_g = "regg" in clean_fmt or "vgc2016" in clean_fmt or "vgc2019" in clean_fmt or "vgc2022" in clean_fmt
    allow_restricted = is_reg_g or "ubers" in clean_fmt or "anythinggoes" in clean_fmt
    allow_sublegends_and_paradox = not is_reg_h

    singles_banned_tiers, doubles_banned_tiers = get_tier_banlist_for_format(clean_fmt, is_doubles)
    champions_legal_set = await get_champions_legal_pokemon() if is_champions else set()
    live_chaos = await fetch_live_format_chaos(clean_fmt)

    # 1. Filtrado de Pokémon
    legal_pokemon: Dict[str, Dict[str, Any]] = {}

    for poke_id, p in POKEDEX_DB.items():
        base_clean = normalize_id(p.get("baseSpecies") or p.get("name") or "")

        # SISTEMA DE LISTA BLANCA ABSOLUTO: 
        # Si el formato tiene "whitelist", ignoramos todas las demás reglas complejas.
        if whitelist_set:
            if poke_id in whitelist_set or base_clean in whitelist_set:
                # Solo comprobamos si las megas están permitidas
                if p.get("is_mega") and not allow_megas:
                    continue
                legal_pokemon[poke_id] = p
            continue # Si no está en la lista blanca, pasa al siguiente Pokémon de inmediato.

        # ----- REGLAS ESTÁNDAR (Si no hay Whitelist) -----
        if p.get("num", 9999) > max_dex_num: continue
        if not is_forme_valid_in_gen(p, gen_num, is_champions): continue
        if p.get("is_mega") and not allow_megas: continue
        if p.get("is_primal") and not is_natdex and "ubers" not in clean_fmt: continue

        if is_champions and champions_legal_set:
            if poke_id not in champions_legal_set and base_clean not in champions_legal_set:
                continue

        is_restr = (
            bool(p.get("is_restricted"))
            or base_clean in RESTRICTED_SPECIES
            or poke_id in RESTRICTED_SPECIES
            or bool(POKEDEX_DB.get(base_clean, {}).get("is_restricted"))
        )
        if is_restr and not allow_restricted: continue
        if p.get("is_mythical") and ("vgc" in clean_fmt or is_champions or not allow_restricted): continue
        if not allow_sublegends_and_paradox and (p.get("is_sublegend") or p.get("is_paradox")): continue

        p_tier = str(p.get("tier") or "").lower()
        p_doubles_tier = str(p.get("doubles_tier") or p.get("doublesTier") or "").lower()
        if p_tier == "unspecified" and base_clean in {"arceus", "meowstic"}:  # estas formas heredan el tier de su especie base
            _b = POKEDEX_DB.get(base_clean, {})
            p_tier = str(_b.get("tier") or "").lower() or p_tier
            p_doubles_tier = str(_b.get("doubles_tier") or _b.get("doublesTier") or "").lower() or p_doubles_tier

        if is_doubles and p_doubles_tier in doubles_banned_tiers: continue
        if not is_doubles and p_tier in singles_banned_tiers: continue
        if poke_id in banlist_set or base_clean in banlist_set: continue

        # Formas solo de combate/cosméticas (Aegislash-Blade, Ogerpon-Tera...) no se pueden elegir en el equipo
        if p_tier == "unspecified" and base_clean not in {"arceus", "meowstic"}: continue
        # Gen 9 por tiers: "Illegal" = no existe en el juego (ej. Caterpie, Alakazam); Champions usa su propia lista
        if gen_num == 9 and not is_natdex and not is_champions and p_tier == "illegal": continue

        legal_pokemon[poke_id] = p

    # 2. Movimientos e Ítems disponibles (Lógica simplificada)
    legal_moves = {k: v for k, v in MOVES_DB.items() if k not in banlist_set}
    legal_items = {}
    if gen_num > 1:
        for item_id, item in ITEMS_DB.items():
            if item_id in banlist_set: continue
            if item.get("megaStone") and not allow_megas: continue
            if item.get("isZ") and not allow_z_moves: continue
            legal_items[item_id] = item

    max_restricted = 2 if ("vgc2016" in clean_fmt or "vgc2019" in clean_fmt) else (1 if is_reg_g else (6 if allow_restricted else 0))

    return {
        "format": fmt_info,
        "mechanics": {
            "gen": gen_num,
            "allow_tera": allow_tera,
            "allow_megas": allow_megas,
            "allow_z_moves": allow_z_moves,
            "allow_dynamax": allow_dynamax,
            "force_mega": allow_megas,
            "force_z_move": allow_z_moves,
            "allow_items": gen_num > 1,
            "allow_abilities": gen_num >= 3,
            "max_megas": 1 if allow_megas else 0,
            "max_restricted": max_restricted,
            "force_restricted": allow_restricted and ("ubers" in clean_fmt or is_reg_g),
            "item_clause": "vgc" in clean_fmt or "itemclause" in ruleset_str or is_champions,
        },
        "legal_pokemon": legal_pokemon,
        "legal_items": legal_items,
        "legal_moves": legal_moves,
    }