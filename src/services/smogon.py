"""
Motor de búsqueda competitiva en vivo (Live Meta Scraper) Multigeneracional (Gen 1 a Gen 9).
Consulta las estadísticas y sets propios de la generación seleccionada sin mezclar generaciones.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("uvicorn")

LIVE_STATS_CACHE: Dict[str, Dict[str, Any]] = {}
LIVE_SETS_CACHE: Dict[str, Dict[str, Any]] = {}
LATEST_SMOGON_MONTH: Optional[str] = None

PKMN_STATS_BASE = "https://pkmn.github.io/smogon/data/stats"
PKMN_SETS_BASE = "https://pkmn.github.io/smogon/data/sets"
SMOGON_OFFICIAL_STATS_URL = "https://www.smogon.com/stats/"


def normalize_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def normalize_species_key(species: str) -> str:
    return normalize_id(species)


async def get_latest_smogon_month(client: httpx.AsyncClient) -> str:
    global LATEST_SMOGON_MONTH
    if LATEST_SMOGON_MONTH:
        return LATEST_SMOGON_MONTH

    try:
        resp = await client.get(SMOGON_OFFICIAL_STATS_URL)
        if resp.status_code == 200:
            months = re.findall(r'href="(\d{4}-\d{2})/"', resp.text)
            if months:
                LATEST_SMOGON_MONTH = sorted(months)[-1]
                logger.info(f"==> Último mes de Smogon detectado: {LATEST_SMOGON_MONTH}")
                return LATEST_SMOGON_MONTH
    except Exception as e:
        logger.warning(f"No se pudo consultar el índice de meses de Smogon: {e}")

    return "2026-03"


async def fetch_live_format_chaos(format_id: str) -> Dict[str, Any]:
    clean_fmt = normalize_id(format_id)
    if clean_fmt in LIVE_STATS_CACHE:
        return LIVE_STATS_CACHE[clean_fmt]

    gen_match = re.match(r"^gen([1-9])", clean_fmt)
    gen_num = int(gen_match.group(1)) if gen_match else 9

    is_champions = "champion" in clean_fmt
    is_doubles = any(k in clean_fmt for k in ["vgc", "doubles", "bss"])

    # Mantener los fallbacks ESTRICTAMENTE dentro de la misma generación
    if is_champions:
        candidate_formats = [
            clean_fmt,
            "gen9championsvgc2026regmc",
            "gen9championsvgc2026regmcbo3",
            "gen9championsbssregmc",
            "gen9championsou",
        ]
    elif gen_num < 9:
        if is_doubles:
            candidate_formats = [clean_fmt, f"gen{gen_num}doublesou", f"gen{gen_num}ou"]
        else:
            candidate_formats = [clean_fmt, f"gen{gen_num}ou", f"gen{gen_num}uu", f"gen{gen_num}ubers"]
    elif is_doubles:
        candidate_formats = [
            clean_fmt,
            "gen9vgc2025regg",
            "gen9vgc2024regh",
            "gen9vgc2024regg",
            "gen9vgc2024regf",
            "gen9doublesou",
        ]
    else:
        candidate_formats = [clean_fmt, "gen9ou", "gen9nationaldex", "gen9uu", "gen9ubers"]

    seen_fmt = set()
    ordered_formats = []
    for f in candidate_formats:
        if f not in seen_fmt:
            seen_fmt.add(f)
            ordered_formats.append(f)

    combined_pokemon_stats: Dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        latest_month = await get_latest_smogon_month(client)
        for fmt in ordered_formats:
            for rating in ["1500", "0"]:
                chaos_url = f"{SMOGON_OFFICIAL_STATS_URL}{latest_month}/chaos/{fmt}-{rating}.json"
                try:
                    r = await client.get(chaos_url)
                    if r.status_code == 200:
                        raw_chaos = r.json().get("data", {})
                        if raw_chaos:
                            logger.info(f"==> Estadísticas en vivo cargadas ({latest_month}/{fmt}-{rating})")
                            for sp_name, sp_data in raw_chaos.items():
                                k = normalize_id(sp_name)
                                if k not in combined_pokemon_stats:
                                    combined_pokemon_stats[k] = {
                                        "name": sp_name,
                                        "usage": sp_data.get("usage", 0),
                                        "abilities": sp_data.get("Abilities", {}),
                                        "items": sp_data.get("Items", {}),
                                        "moves": sp_data.get("Moves", {}),
                                        "spreads": sp_data.get("Spreads", {}),
                                        "teammates": sp_data.get("Teammates", {}),
                                    }
                            break
                except Exception:
                    continue
            if combined_pokemon_stats and fmt == clean_fmt:
                break

        for fmt in ordered_formats:
            try:
                r = await client.get(f"{PKMN_STATS_BASE}/{fmt}.json")
                if r.status_code == 200:
                    p_map = r.json().get("pokemon", {})
                    for sp_name, sp_data in p_map.items():
                        k = normalize_id(sp_name)
                        if k not in combined_pokemon_stats:
                            combined_pokemon_stats[k] = {
                                "name": sp_name,
                                "usage": sp_data.get("usage", {}).get("weighted", 0),
                                "abilities": sp_data.get("abilities", {}),
                                "items": sp_data.get("items", {}),
                                "moves": sp_data.get("moves", {}),
                                "spreads": sp_data.get("spreads", {}),
                                "teammates": sp_data.get("teammates", {}),
                            }
                    if len(combined_pokemon_stats) > 40:
                        break
            except Exception:
                continue

    LIVE_STATS_CACHE[clean_fmt] = combined_pokemon_stats
    return combined_pokemon_stats


async def fetch_smogon_sets(format_id: str) -> Dict[str, Any]:
    clean_id = normalize_id(format_id)
    if clean_id in LIVE_SETS_CACHE:
        return LIVE_SETS_CACHE[clean_id]

    gen_match = re.match(r"^gen([1-9])", clean_id)
    gen_num = int(gen_match.group(1)) if gen_match else 9
    is_champions = "champion" in clean_id
    is_doubles = any(k in clean_id for k in ["vgc", "doubles"])

    if is_champions:
        fallbacks = [clean_id, "gen9championsvgc2026regmc", "gen9championsou"]
    elif gen_num < 9:
        fallbacks = [clean_id, f"gen{gen_num}.json".replace(".json", ""), f"gen{gen_num}ou", f"gen{gen_num}uu"]
    elif is_doubles:
        fallbacks = [clean_id, "gen9vgc2024regh", "gen9vgc2024regg", "gen9doublesou"]
    else:
        fallbacks = [clean_id, "gen9ou", "gen9uu"]

    combined_sets: Dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=6.0) as client:
        for fmt in fallbacks:
            try:
                resp = await client.get(f"{PKMN_SETS_BASE}/{fmt}.json")
                if resp.status_code == 200:
                    data = resp.json()
                    for sp_name, sets_dict in data.items():
                        k = normalize_id(sp_name)
                        if k not in combined_sets:
                            combined_sets[k] = sets_dict
            except Exception:
                continue

    LIVE_SETS_CACHE[clean_id] = combined_sets
    return combined_sets


def parse_spread_string(spread_str: str) -> Tuple[str, Dict[str, int]]:
    try:
        nature, evs_part = spread_str.split(":")
        nums = [int(x) for x in evs_part.split("/")]
        if len(nums) == 6:
            return nature, {
                "hp": nums[0],
                "atk": nums[1],
                "defense": nums[2],
                "sp_atk": nums[3],
                "sp_def": nums[4],
                "speed": nums[5],
            }
    except Exception:
        pass
    return "Adamant", {"hp": 252, "atk": 252, "defense": 0, "sp_atk": 0, "sp_def": 4, "speed": 0}