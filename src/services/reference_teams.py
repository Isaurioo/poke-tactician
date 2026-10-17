"""Equipos de referencia ("el campeón del mundial 2024", "Big 6", "equipo popular de VGC 2015", un jugador, un arquetipo...).

Principio: la IA NO es la fuente de verdad. Cada pedido se resuelve con la fuente más fiable disponible y la respuesta
dice siempre de dónde salió:

  1. "kb"     Equipo verificado de src/data/known_teams.json (con fuente y forma exacta de cada Pokémon).
  2. "web"    BÚSQUEDA WEB en vivo (web_lookup.py) para cualquier equipo concreto, con las fuentes consultadas.
  3. "big6" / "usage"  Respaldo si la web falla: estadísticas REALES de uso del formato EXACTO elegido (Smogon stats).
  4. "recall" Memoria del modelo, marcada como NO VERIFICADA; lo que no sea legal se sustituye con uso real.

El motor valida cada especie contra el formato (legalidad, Megas, restringidos); este módulo no relaja ninguna regla.
"""
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple

import httpx

from src.core.entity_extraction import resolve_species_name
from src.services import pokedex_service
from src.services.smogon import LIVE_STATS_META, fetch_live_format_chaos, normalize_id

logger = logging.getLogger("uvicorn")

KNOWN_TEAMS_PATH = Path(__file__).resolve().parents[1] / "data" / "known_teams.json"
_KB_CACHE: Optional[List[Dict[str, Any]]] = None


# --------------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------------
def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", t).strip()


def load_known_teams() -> List[Dict[str, Any]]:
    global _KB_CACHE
    if _KB_CACHE is None:
        try:
            data = json.loads(KNOWN_TEAMS_PATH.read_text(encoding="utf-8"))
            _KB_CACHE = [t for t in data.get("teams", []) if isinstance(t, dict) and len(t.get("species", [])) >= 4]
        except Exception as err:
            logger.warning(f"known_teams.json no disponible: {err}")
            _KB_CACHE = []
    return _KB_CACHE


# --------------------------------------------------------------------------------------------
# 1) Equipos verificados: se eligen por puntuación de rasgos (año, evento, puesto, jugador, alias)
# --------------------------------------------------------------------------------------------
_EVENT_PATTERNS = {
    "worlds": r"\b(mundial\w*|worlds?|world championships?|campeonato mundial)\b",
    "regional": r"\bregional\w*\b",
    "international": r"\b(internacional\w*|international\w*|naic|euic|laic|ocic|svic)\b",
    "national": r"\b(nacional\w*|nationals?)\b",
}


def _query_traits(prompt: str) -> Dict[str, Any]:
    t = _plain(prompt)
    year = re.search(r"\b(20[0-3]\d)\b", t)
    event = next((k for k, p in _EVENT_PATTERNS.items() if re.search(p, t)), None)
    placing = None
    if re.search(r"\b(campeon\w*|champion|ganador\w*|winner|vainqueur)\b", t):
        placing = 1
    elif re.search(r"\b(finalista\w*|subcampeon\w*|runner[- ]?up)\b", t):
        placing = 2
    elif re.search(r"\b(semifinalista\w*|top\s*4)\b", t):
        placing = 4
    elif re.search(r"\btop\s*8\b", t):
        placing = 8
    return {"text": t, "squashed": normalize_id(t), "year": int(year.group(1)) if year else None,
            "event": event, "placing": placing}


def match_known_team(prompt: str, format_id: str = "") -> Optional[Dict[str, Any]]:
    """Mejor equipo verificado para el pedido, o None. Es estricto: año, evento y puesto pedidos deben coincidir."""
    q = _query_traits(prompt)
    best: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)
    for team in load_known_teams():
        score = 0.0
        player_hit = bool(team.get("player")) and normalize_id(team["player"]) in q["squashed"]
        alias_hit = any(normalize_id(a) and normalize_id(a) in q["squashed"] for a in team.get("aliases", []))
        if q["year"] is not None and team.get("year") != q["year"]:
            continue
        if q["year"] is not None:
            score += 3
        if q["event"] is not None:
            if team.get("event_type") != q["event"]:
                continue
            score += 2
        pl = team.get("placing")
        if q["placing"] is not None:
            if q["placing"] == 1 and pl != 1:
                continue
            if q["placing"] == 2 and pl != 2:
                continue
            if q["placing"] in (4, 8) and (pl is None or pl > q["placing"]):
                continue
            score += 3
        if player_hit:
            score += 6
        if alias_hit:
            score += 6
        if not (player_hit or alias_hit) and (q["event"] is None and q["year"] is None):
            continue  # sin ningún ancla (año, evento, jugador o alias) no se adivina
        if team.get("format_id") and normalize_id(format_id) == normalize_id(team["format_id"]):
            score += 4
        if team.get("division", "masters") == "masters":
            score += 0.5
        score += (team.get("year", 2000) - 2000) * 0.01  # desempate: el más reciente
        if score >= 5 and score > best[0]:
            best = (score, team)
    return best[1]


# --------------------------------------------------------------------------------------------
# 2) Estadísticas de uso del formato EXACTO (sin fallbacks a otros formatos)
# --------------------------------------------------------------------------------------------
async def fetch_exact_format_usage(format_id: str) -> Optional[Dict[str, Any]]:
    """{'meta': {...origen...}, 'pokemon': {nombre: {'usage','teammates','items'}}} SOLO del formato exacto, o None.
    Usa la misma fuente (y caché) que los sets, que ya prioriza el formato exacto y marca los respaldos con `fallback_from`."""
    fid = normalize_id(format_id)
    try:
        data = await fetch_live_format_chaos(fid)
    except Exception as err:
        logger.warning(f"Uso exacto de {fid} no disponible: {err}")
        return None
    exact = {e.get("name", k): e for k, e in data.items() if not e.get("fallback_from")}
    if len(exact) < 12:
        return None
    meta = LIVE_STATS_META.get(fid) or {"month": "?", "rating": "?", "format": fid, "source": "?"}
    pokemon = {n: {"usage": float(e.get("usage", 0) or 0), "teammates": e.get("teammates") or {}, "items": e.get("items") or {}}
               for n, e in exact.items()}
    return {"meta": meta, "pokemon": pokemon}


def _resolve_name(raw: str, cache: Any, legal_map: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Como resolve_species_name, pero "Groudon-Primal"/"Kyogre-Primal" (así aparecen en las estadísticas y en las fuentes)
    se resuelven a la especie base cuando la forma primigenia no es un Pokémon aparte del formato: se activa con la orbe."""
    entry = resolve_species_name(str(raw), cache, legal_map)
    if entry is None and re.search(r"[- ]primal$", str(raw).strip(), flags=re.I):
        entry = resolve_species_name(re.sub(r"[- ]primal$", "", str(raw).strip(), flags=re.I), cache, legal_map)
    return entry


def fit_roster(raw_names: List[str], legal_map: Dict[str, Any], cache: Any,
               mega_cap: int, max_restricted: int, limit: int = 6) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Convierte nombres en entradas LEGALES del formato respetando Megas/restringidos/especie única.
    Devuelve (conservados, descartados)."""
    kept: List[Dict[str, Any]] = []
    dropped: List[str] = []
    bases: Set[str] = set()
    megas = restricted = 0
    for raw in raw_names:
        entry = _resolve_name(str(raw), cache, legal_map)
        if not entry:
            dropped.append(str(raw))  # no existe o no es legal en este formato
            continue
        base = normalize_id(entry.get("baseSpecies") or entry.get("name") or "")
        if base in bases or len(kept) >= limit:
            dropped.append(str(raw))
            continue
        if entry.get("is_mega") and megas >= mega_cap:
            dropped.append(str(raw))
            continue
        if entry.get("is_restricted") and max_restricted and restricted >= max_restricted:
            dropped.append(str(raw))
            continue
        bases.add(base)
        megas += bool(entry.get("is_mega"))
        restricted += bool(entry.get("is_restricted"))
        kept.append(entry)
    return kept, dropped


def build_usage_team(stats: Dict[str, Any], legal_map: Dict[str, Any], cache: Any, *,
                     mode: str, seeds: Optional[List[Dict[str, Any]]] = None,
                     mega_cap: int = 1, max_restricted: int = 0, size: int = 6,
                     force_mega: bool = False) -> List[Dict[str, Any]]:
    """mode='big6': los más usados, uno a uno.  mode='core': núcleo coherente (compañeros frecuentes).
    `seeds` (entradas ya elegidas) se conservan y el resto se completa con uso real."""
    pokemon = stats["pokemon"]
    key_of: Dict[str, str] = {normalize_id(n): n for n in pokemon}
    rows: List[Tuple[float, str, Dict[str, Any]]] = []
    for name, d in pokemon.items():
        entry = _resolve_name(name, cache, legal_map)
        if entry:
            rows.append((float(d.get("usage", 0) or 0), name, entry))
    rows.sort(key=lambda r: -r[0])
    if not rows:
        return []
    top_usage = rows[0][0] or 1.0

    def _stats_key(entry: Dict[str, Any]) -> Optional[str]:
        return key_of.get(normalize_id(entry.get("name", ""))) or key_of.get(normalize_id(entry.get("baseSpecies", "")))

    def _affinity(a_key: Optional[str], b_name: str) -> float:
        if not a_key:
            return 0.0
        row = pokemon[a_key].get("teammates") or {}
        vals = [v for v in row.values() if isinstance(v, (int, float)) and v > 0]
        if not vals:
            return 0.0
        v = row.get(b_name, 0)
        return max(0.0, min(1.0, (v / max(vals)) if isinstance(v, (int, float)) else 0.0))

    chosen: List[Dict[str, Any]] = []
    bases: Set[str] = set()
    megas = restricted = 0

    def _try_add(entry: Dict[str, Any]) -> bool:
        nonlocal megas, restricted
        base = normalize_id(entry.get("baseSpecies") or entry.get("name") or "")
        if base in bases or len(chosen) >= size:
            return False
        if entry.get("is_mega") and megas >= mega_cap:
            return False
        if entry.get("is_restricted") and max_restricted and restricted >= max_restricted:
            return False
        bases.add(base)
        megas += bool(entry.get("is_mega"))
        restricted += bool(entry.get("is_restricted"))
        chosen.append(entry)
        return True

    def _megaify(team: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Las estadísticas antiguas agrupan la Mega bajo su especie base (con la piedra como objeto). Si la piedra es el
        objeto dominante y el formato permite Megas, el equipo usa la Mega (respetando el tope)."""
        current = sum(1 for e in team if e.get("is_mega"))
        out = list(team)
        for i, e in enumerate(out):
            if current >= mega_cap:
                break
            if e.get("is_mega"):
                continue
            key = _stats_key(e)
            items = (pokemon[key].get("items") if key else None) or {}
            total = sum(v for v in items.values() if isinstance(v, (int, float))) or 0
            if not total:
                continue
            shares = {normalize_id(k): v / total for k, v in items.items() if isinstance(v, (int, float))}
            best: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)
            for m in legal_map.values():
                if not isinstance(m, dict) or not m.get("is_mega") or m.get("baseSpecies") != e.get("baseSpecies"):
                    continue
                share = shares.get(normalize_id(m.get("requiredItem") or ""), 0.0)
                if share > best[0]:
                    best = (share, m)
            if best[1] is not None and best[0] >= 0.5:
                out[i] = best[1]
                current += 1
        # Respaldo: si el formato exige Mega (Gen 6/7, Champions) y las estadísticas no dejaron ver ninguna, el integrante
        # más usado que tenga una Mega legal la usa (con su mejor Mega por stats base).
        if force_mega and mega_cap > 0 and current == 0:
            options: List[Tuple[float, int, Dict[str, Any]]] = []
            for i, e in enumerate(out):
                key = _stats_key(e)
                megas_of = [m for m in legal_map.values() if isinstance(m, dict) and m.get("is_mega")
                            and m.get("baseSpecies") == e.get("baseSpecies")]
                if megas_of:
                    best_m = max(megas_of, key=lambda m: sum((m.get("baseStats") or {}).values()))
                    options.append((float(pokemon[key].get("usage", 0) or 0) if key else 0.0, i, best_m))
            if options:
                _u, i, m = max(options, key=lambda o: o[0])
                out[i] = m
        return out

    for s in seeds or []:
        _try_add(s)

    if mode == "big6":
        for _u, _n, entry in rows:
            if len(chosen) >= size:
                break
            _try_add(entry)
        return _megaify(chosen)

    while len(chosen) < size:
        best: Tuple[float, Optional[Dict[str, Any]]] = (-1.0, None)
        chosen_keys = [_stats_key(c) for c in chosen]
        for usage, name, entry in rows:
            base = normalize_id(entry.get("baseSpecies") or entry.get("name") or "")
            if base in bases or (entry.get("is_mega") and megas >= mega_cap):
                continue
            if entry.get("is_restricted") and max_restricted and restricted >= max_restricted:
                continue
            if chosen:
                aff = sum(_affinity(k, name) for k in chosen_keys) / len(chosen)
                score = aff + 0.35 * (usage / top_usage)
            else:
                score = usage / top_usage
            if score > best[0]:
                best = (score, entry)
        if best[1] is None or not _try_add(best[1]):
            break
    return _megaify(chosen)


# --------------------------------------------------------------------------------------------
# Orquestador
# --------------------------------------------------------------------------------------------
RecallFn = Callable[[str, Dict[str, Any], int], Awaitable[Optional[Dict[str, Any]]]]
WebFn = Callable[[str, Dict[str, Any], int], Awaitable[Optional[Dict[str, Any]]]]


async def resolve_reference_team(
    prompt: str,
    intent: Dict[str, Any],
    pool: Dict[str, Any],
    bring_n: int,
    mega_cap: int,
    recall_fn: RecallFn,
    web_fn: Optional[WebFn] = None,
) -> Optional[Dict[str, Any]]:
    """Devuelve {'kind','source','url','resolved','dropped','filled','origin_format','usage_meta'} o None.
    kind: 'kb' | 'web' | 'big6' | 'usage' | 'recall'. Orden: equipo verificado -> BÚSQUEDA WEB -> uso real del formato
    (solo Big 6 / popular) -> memoria del modelo. Nunca devuelve entradas ilegales para el formato del pool."""
    legal_map = pool["legal_pokemon"]
    pokedex_service._load_compendium_files()
    cache = pokedex_service._POKEDEX_CACHE
    mech = pool["mechanics"]
    max_restricted = int(mech.get("max_restricted", 0) or 0)
    fmt_id = pool["format"].get("id") or pool["format"].get("format_id") or ""

    async def _usage() -> Optional[Dict[str, Any]]:
        return await fetch_exact_format_usage(fmt_id) if fmt_id else None

    def _result(kind: str, source: str, kept: List[Dict[str, Any]], dropped: List[str], **extra: Any) -> Dict[str, Any]:
        return {"kind": kind, "source": source, "url": extra.get("url"), "resolved": kept, "dropped": dropped,
                "filled": extra.get("filled", 0), "origin_format": extra.get("origin_format"),
                "usage_meta": extra.get("usage_meta"), "web": extra.get("web"), "web_failed": extra.get("web_failed", False),
                "paste_urls": extra.get("paste_urls", [])}

    async def _complete(kept: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int, Optional[Dict[str, Any]]]:
        """Si faltan integrantes, se completan con uso real del formato elegido (seguido por lo que sí se conservó)."""
        if not kept or len(kept) >= 6:
            return kept, 0, None
        stats = await _usage()
        if not stats:
            return kept, 0, None
        full = build_usage_team(stats, legal_map, cache, mode="core", seeds=kept, mega_cap=min(mega_cap, 2),
                                max_restricted=max_restricted, force_mega=bool(mech.get("force_mega")))
        return full, max(0, len(full) - len(kept)), stats["meta"]

    # 1) Equipo verificado
    kb = match_known_team(prompt, fmt_id)
    if kb:
        kept, dropped = fit_roster(kb["species"], legal_map, cache, mega_cap, max_restricted)
        origin = kb.get("format_id") if normalize_id(kb.get("format_id", "")) != normalize_id(fmt_id) else None
        label = f"{kb.get('event', '')} - {kb.get('player', '')}".strip(" -")
        full, filled, meta = await _complete(kept)
        return _result("kb", label, full, dropped, url=kb.get("source"), filled=filled,
                       origin_format=origin, usage_meta=meta, paste_urls=[kb["paste"]] if kb.get("paste") else [])

    # 2) BÚSQUEDA WEB en vivo (cualquier equipo concreto: torneo, jugador, Big 6, popular, arquetipo)
    web_failed = False
    if web_fn is not None:
        web = await web_fn(prompt, pool, bring_n)
        if web:
            kept, dropped = fit_roster(web["species"], legal_map, cache, mega_cap, max_restricted)
            full, filled, meta = await _complete(kept)
            return _result("web", web["source"], full, dropped, url=", ".join(web.get("sources", [])), filled=filled,
                           usage_meta=meta, web=web, paste_urls=[u for u in web.get("sources", []) if "pokepast.es" in u])
        web_failed = True

    # 3) Big 6 / equipo popular genérico: uso real del formato exacto (respaldo si la web no respondió)
    if intent.get("wants_big6") or intent.get("wants_generic_popular"):
        stats = await _usage()
        if stats:
            mode = "big6" if intent.get("wants_big6") else "core"
            team = build_usage_team(stats, legal_map, cache, mode=mode, mega_cap=min(mega_cap, 2), max_restricted=max_restricted,
                                    force_mega=bool(mech.get("force_mega")))
            if len(team) >= 6:
                return _result("big6" if mode == "big6" else "usage",
                               "Big 6" if mode == "big6" else "equipo más usado",
                               team, [], usage_meta=stats["meta"], web_failed=web_failed)

    # 4) Memoria del modelo (no verificada); lo ilegal se sustituye con uso real
    data = await recall_fn(prompt, pool, bring_n)
    if not data:
        return None
    kept, dropped = fit_roster([str(x) for x in data["species"][:6]], legal_map, cache, mega_cap, max_restricted)
    full, filled, meta = await _complete(kept)
    return _result("recall", data.get("source", "equipo de referencia"), full, dropped, filled=filled, usage_meta=meta,
                   web_failed=web_failed)


# --------------------------------------------------------------------------------------------
# Sets reales desde un Pokepaste (equipo de torneo con enlace)
# --------------------------------------------------------------------------------------------
async def fetch_paste_sets(urls: List[str]) -> List[Dict[str, Any]]:
    """Lee Pokepastes (pokepast.es/<id>/raw) y devuelve los sets (formato del parser del analizador). Mejor esfuerzo."""
    from src.api.routes_analyzer import parse_showdown_team  # import tardío: evita cargar el analizador al importar

    for u in urls[:3]:
        if "pokepast.es" not in u:
            continue
        base = u.strip().rstrip("/")
        raw_url = base if base.endswith("/raw") else base + "/raw"
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                r = await client.get(raw_url)
            if r.status_code == 200 and r.text.strip():
                sets = parse_showdown_team(r.text)
                if len(sets) >= 4:
                    return sets
        except Exception as err:
            logger.warning(f"Pokepaste no disponible ({raw_url}): {err}")
    return []


def pseudo_stats_from_sets(sets: List[Dict[str, Any]], legal_map: Dict[str, Any], cache: Any) -> Dict[str, Any]:
    """Convierte sets reales en 'estadísticas' con 100% de uso (misma forma que live_chaos) para que el generador los
    elija. Solo se aceptan especies legales en el formato; la legalidad de objeto/ataques la sigue filtrando el motor."""
    big = 100000.0
    out: Dict[str, Any] = {}
    for st in sets:
        entry = resolve_species_name(str(st.get("species", "")), cache, legal_map)
        if not entry:
            continue
        evs = st.get("evs") or {}
        spread = ":".join([st.get("nature") or "Hardy",
                           "/".join(str(int(evs.get(k, 0))) for k in ("hp", "atk", "defense", "sp_atk", "sp_def", "speed"))])
        out[normalize_id(entry["name"])] = {
            "name": entry["name"], "usage": 1.0,
            "abilities": {st["ability"]: big} if st.get("ability") else {},
            "items": {st["item"]: big} if st.get("item") else {},
            "moves": {m: big for m in (st.get("moves") or [])[:4]},
            "spreads": {spread: big} if st.get("nature") and evs else {},
            "teammates": {},
        }
    return out
