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


LIVE_STATS_META: Dict[str, Dict[str, Any]] = {}  # origen de los datos del formato EXACTO (mes, rating, fuente)
_STATS_RATINGS = ("1500", "0", "1630", "1760")


def months_back(latest: str, n: int) -> List[str]:
    """['2026-07', '2026-06', ...]: el mes más reciente y los n-1 anteriores."""
    try:
        y, m = (int(x) for x in latest.split("-"))
    except Exception:
        return [latest]
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def _rescale_weights(d: Any) -> Any:
    """El generador de sets espera pesos tipo CONTEO (miles). Si la fuente trae fracciones o porcentajes, los bonos fijos de
    sinergia (cientos de puntos) aplastaban el uso real y salían objetos "de moda" en vez de los usados. Si el total es
    pequeño se reescala a 100000, de modo que el uso real manda y los bonos solo desempatan."""
    if not isinstance(d, dict):
        return d
    total = sum(v for v in d.values() if isinstance(v, (int, float)))
    if 0 < total < 10000:
        f = 100000.0 / total
        return {k: (v * f if isinstance(v, (int, float)) else v) for k, v in d.items()}
    return d


def _stats_entry(sp_name: str, usage: Any, abilities: Any, items: Any, moves: Any, spreads: Any, teammates: Any) -> Dict[str, Any]:
    return {
        "name": sp_name,
        "usage": usage,
        "abilities": _rescale_weights(abilities or {}),
        "items": _rescale_weights(items or {}),
        "moves": _rescale_weights(moves or {}),
        "spreads": _rescale_weights(spreads or {}),
        "teammates": teammates or {},
    }


async def fetch_live_format_chaos(format_id: str) -> Dict[str, Any]:
    """Estadísticas de uso por especie. Prioridad: (1) el formato EXACTO (Smogon, últimos 3 meses, y pkmn.github.io);
    (2) solo si el exacto casi no tiene datos, formatos de respaldo de la misma generación, con la marca `fallback_from`.
    Antes los formatos de respaldo (Doubles OU, OU) se cargaban primero y pisaban los datos del formato exacto."""
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

    ordered_formats = list(dict.fromkeys(candidate_formats))
    combined_pokemon_stats: Dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        latest_month = await get_latest_smogon_month(client)

        async def smogon_chaos(fmt: str, months: List[str]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
            for month in months:
                for rating in _STATS_RATINGS:
                    try:
                        r = await client.get(f"{SMOGON_OFFICIAL_STATS_URL}{month}/chaos/{fmt}-{rating}.json")
                        if r.status_code != 200:
                            continue
                        raw_chaos = r.json().get("data", {})
                    except Exception:
                        continue
                    if raw_chaos:
                        logger.info(f"==> Estadísticas en vivo cargadas ({month}/{fmt}-{rating})")
                        out = {normalize_id(n): _stats_entry(n, d.get("usage", 0), d.get("Abilities"), d.get("Items"),
                                                             d.get("Moves"), d.get("Spreads"), d.get("Teammates"))
                               for n, d in raw_chaos.items()}
                        return out, {"month": month, "rating": rating, "source": "smogon.com"}
            return {}, None

        async def pkmn_stats(fmt: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
            try:
                r = await client.get(f"{PKMN_STATS_BASE}/{fmt}.json")
                if r.status_code == 200:
                    p_map = r.json().get("pokemon", {})
                    if p_map:
                        out = {normalize_id(n): _stats_entry(n, (d.get("usage") or {}).get("weighted", 0), d.get("abilities"),
                                                             d.get("items"), d.get("moves"), d.get("spreads"), d.get("teammates"))
                               for n, d in p_map.items()}
                        return out, {"month": "pkmn.github.io", "rating": "-", "source": "pkmn.github.io"}
            except Exception:
                pass
            return {}, None

        # 1) Formato EXACTO: siempre antes que cualquier respaldo
        exact, meta = await smogon_chaos(clean_fmt, months_back(latest_month, 3))
        if len(exact) <= 40:
            alt, alt_meta = await pkmn_stats(clean_fmt)
            for k, v in alt.items():
                exact.setdefault(k, v)
            meta = meta or alt_meta
        combined_pokemon_stats.update(exact)
        if meta:
            LIVE_STATS_META[clean_fmt] = {**meta, "format": clean_fmt}

        # 2) Respaldo (misma generación) solo si el formato exacto casi no tiene datos
        if len(combined_pokemon_stats) <= 40:
            for fmt in ordered_formats[1:]:
                for fetch in (lambda f=fmt: smogon_chaos(f, [latest_month]), lambda f=fmt: pkmn_stats(f)):
                    data, _m = await fetch()
                    for k, v in data.items():
                        if k not in combined_pokemon_stats:
                            combined_pokemon_stats[k] = {**v, "fallback_from": fmt}
                if len(combined_pokemon_stats) > 40:
                    break

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