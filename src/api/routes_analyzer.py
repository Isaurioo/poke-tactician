"""Analizador de equipos: solo informa. Mismas reglas, fichas y guía táctica que el creador."""
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.routes_teambuilder import make_strategy_guide
from src.core.coverage import (get_ability_description_es, get_item_description_es,
                               get_move_rich_details, get_nature_description_es)
from src.core.era_rules import effectiveness, era_mechanics, era_types, type_chart_for_gen
from src.core.messages import msg, norm_lang
from src.core.optimizer import calculate_level_50_stats, compute_accurate_role_label
from src.core.suggestions import make_suggestions
from src.core.team_validator import audit_team
from src.core.types import compute_defensive_matchups
from src.services.format_engine import filter_available_pool_for_format
from src.services.pokedex_service import _load_compendium_files, _POKEDEX_CACHE, get_species_types
from src.services.smogon import fetch_live_format_chaos, normalize_id as nid
from src.services.teambuilder import (WEATHER_ABILITIES, apply_era_mechanics, build_showdown_sprite_url,
                                      build_versatile_context_for_ai, normalize_base_stats, parse_tactical_intent)
from src.core.entity_extraction import resolve_species_name

router = APIRouter(prefix="", tags=["Analyzer"])
logger = logging.getLogger("uvicorn")

TYPE_CHART = {
    "Normal": {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water": {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
    "Grass": {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
    "Ground": {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying": {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
    "Bug": {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Dark": {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Fairy": {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5},
}

ALL_TYPES = list(TYPE_CHART.keys())


class AnalyzeTeamRequest(BaseModel):
    format_id: str = "gen9championsvgc2026regmc"
    paste: str
    lang: str = "es"


_EV_KEYS = {"hp": "hp", "atk": "atk", "def": "defense", "spa": "sp_atk", "spd": "sp_def", "spe": "speed"}


def parse_showdown_team(paste: str) -> List[Dict[str, Any]]:
    """Lee el export de Showdown: especie, objeto, habilidad, Tera, naturaleza, EVs y movimientos."""
    blocks = re.split(r"\n\s*\n", paste.replace("\r\n", "\n").replace("\r", "\n").strip())
    team = []
    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        first = lines[0]
        item = ""
        if "@" in first:
            first, item = [x.strip() for x in first.split("@", 1)]
        species = re.sub(r"\s*\([MF]\)\s*$", "", first)
        m = re.search(r"\((.*?)\)", species)
        if m:
            species = m.group(1).strip()
        ability = tera = nature = None
        evs: Dict[str, int] = {}
        moves: List[str] = []
        for line in lines[1:]:
            if line.startswith("Ability:"):
                ability = line.split(":", 1)[1].strip()
            elif line.startswith("Tera Type:"):
                tera = line.split(":", 1)[1].strip()
            elif line.startswith("EVs:"):
                for val, stat in re.findall(r"(\d+)\s*(HP|Atk|Def|SpA|SpD|Spe)", line, flags=re.I):
                    evs[_EV_KEYS[stat.lower()]] = int(val)
            elif re.match(r"^\w+\s+Nature$", line, flags=re.I):
                nature = line.split()[0]
            elif line.startswith("-"):
                mv = re.sub(r"^-+\s*", "", line).strip()
                if mv:
                    moves.append(mv)
        team.append({"species": species, "item": item, "ability": ability or "", "tera_type": tera,
                     "nature": nature, "evs": evs, "moves": moves})
    return team


def calculate_team_defensive_matrix(
    team: List[Dict[str, Any]], gen: int = 9, chart: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    chart = chart or TYPE_CHART
    matrix = {}
    for atk_type in chart:
        weak_list, resist_list, immune_list, neutral_list = [], [], [], []
        for member in team:
            sp = member["species"]
            types = era_types(get_species_types(sp), gen)
            mult = effectiveness(chart, atk_type, types, member.get("ability", ""), gen)
            entry = {"species": sp, "multiplier": mult}
            if mult >= 2.0:
                weak_list.append(entry)
            elif mult == 0.0:
                immune_list.append(entry)
            elif mult < 1.0:
                resist_list.append(entry)
            else:
                neutral_list.append(entry)
        matrix[atk_type] = {
            "weak": weak_list, "resist": resist_list, "immune": immune_list, "neutral": neutral_list,
            "weak_count": len(weak_list), "resist_count": len(resist_list) + len(immune_list),
        }
    return matrix


def _build_slot(p: Dict[str, Any], e: Dict[str, Any], pool: Dict[str, Any], gen: int) -> Dict[str, Any]:
    """Ficha con el mismo formato que las del creador (stats, rol, efectos, defensas)."""
    lm = pool["legal_moves"]
    evs = {k: p["evs"].get(k, 0) for k in ("hp", "atk", "defense", "sp_atk", "sp_def", "speed")}
    nature = p["nature"] or "Serious"
    ability = p["ability"] or ""
    moves = p["moves"][:4]
    bs = normalize_base_stats(e.get("baseStats", {}))
    return {
        "species": e["name"], "types": list(e.get("types", [])), "item": p["item"] or None, "ability": ability,
        "tera_type": p["tera_type"], "nature": nature, "evs": evs, "ev_source": "paste", "ev_plan": None,
        "moves": moves,
        "role": compute_accurate_role_label(e, ability, moves, evs, WEATHER_ABILITIES),
        "sprite_url": build_showdown_sprite_url(e), "base_stats": bs,
        "final_stats": calculate_level_50_stats(bs, evs, nature),
        "defensive_matchups": compute_defensive_matchups(list(e.get("types", [])), ability),
        "details": {
            "item_desc": get_item_description_es(p["item"], e.get("baseSpecies", e["name"]), gen) if p["item"] else "",
            "ability_desc": get_ability_description_es(ability, gen) if ability else "",
            "nature_desc": get_nature_description_es(nature),
            "moves_info": [get_move_rich_details(m, lm, gen) for m in moves],
        },
    }


@router.post("/analyze-team")
async def analyze_team_endpoint(req: AnalyzeTeamRequest):
    lang = norm_lang(req.lang)
    if not req.paste or len(req.paste.strip()) < 15:
        raise HTTPException(status_code=400, detail=msg("an_short", lang))
    parsed = parse_showdown_team(req.paste)
    if not parsed:
        raise HTTPException(status_code=400, detail=msg("an_none", lang))

    _load_compendium_files()
    fid = re.sub(r"[^a-z0-9]", "", req.format_id.lower())
    try:
        pool = await filter_available_pool_for_format(fid)
    except Exception as e:
        logger.error(f"Error cargando pool de formato {fid}: {e}")
        raise HTTPException(status_code=400, detail=f"Formato desconocido: {req.format_id}")
    mech = pool["mechanics"]
    gen = int(mech.get("gen", 9) or 9)
    era = era_mechanics(gen)

    # Se resuelve contra TODO el dex (para poder decir "no permitido" en vez de "no existe")
    legal = pool["legal_pokemon"]
    resolve = lambda n: resolve_species_name(n, _POKEDEX_CACHE, legal) or resolve_species_name(n, _POKEDEX_CACHE, _POKEDEX_CACHE)

    pairs = [(p, resolve(p["species"])) for p in parsed]
    audit_slots = [{**p, "species": (e["name"] if e else p["species"])} for p, e in pairs]
    max_megas = mech.get("max_megas", 0)
    errors, warnings = audit_team(audit_slots, pool, resolve, max_megas, lang)

    slots = [_build_slot(p, e, pool, gen) for p, e in pairs if e]
    apply_era_mechanics(slots, gen)
    chart = type_chart_for_gen(TYPE_CHART, gen)
    matrix = calculate_team_defensive_matrix(slots, gen, chart) if slots else {}

    guide: Dict[str, Any] = {}
    suggestions: List[Dict[str, Any]] = []
    suggestions_error: Optional[str] = None
    if slots:
        try:
            live = await fetch_live_format_chaos(fid)
        except Exception:
            live = {}
        _ctx, _req, meta_pool = build_versatile_context_for_ai(pool=pool, live_chaos=live, user_prompt="")
        guide = make_strategy_guide(slots, pool, meta_pool, era, parse_tactical_intent(""),
                                    "Analyze the team pasted by the user", lang)
        try:
            suggestions = make_suggestions(slots, pool, live, matrix, lang, resolve, chart, max_megas)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Fallo al generar sugerencias: {e}")
            suggestions_error = f"{type(e).__name__}"

    return JSONResponse(content={
        "format_id": fid, "format_name": pool["format"]["name"], "team": slots,
        "errors": errors, "warnings": warnings, "rules_ok": not errors,
        "defensive_matrix": matrix, "strategy_guide": guide,
        "suggestions": suggestions, "suggestions_error": suggestions_error, "era": era, "generation": gen, "lang": lang,
    })
