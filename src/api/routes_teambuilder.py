import difflib
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.ai.client import ai_client, MAX_OUTPUT_TOKENS
from openai import APIConnectionError, APIStatusError, RateLimitError
from src.core.entity_extraction import norm_text, resolve_requests, resolve_species_name
from src.core.messages import msg, norm_lang
from src.core.team_validator import RuleViolation, validate_team
from src.core.topic_guard import looks_off_topic
from src.core.era_rules import describe_era, era_mechanics, guide_era_rules
from src.core.move_rules import PROTECT_FAMILY, norm_move
from src.services.format_engine import MAX_DEX_BY_GEN
from src.core.text_validator import drop_era_anachronisms, drop_false_pivot_sentences, sentences
from src.ai.prompts import LANGUAGE_NAMES, SYSTEM_TACTICIAN_PROMPT, SYSTEM_TEAM_SELECTOR_PROMPT, language_rule
from src.api.schemas import TeamGenerationRequest
from src.core.coverage import (
    build_verified_tactical_briefing,
    ensure_showdown_descriptions_loaded,
)
from src.services.format_engine import (
    filter_available_pool_for_format,
    get_official_formats_list,
)
from src.services import pokedex_service
from src.services.smogon import fetch_live_format_chaos, fetch_smogon_sets
from src.services.teambuilder import (
    build_balanced_synergistic_team,
    build_versatile_context_for_ai,
    parse_tactical_intent,
)

router = APIRouter(prefix="", tags=["Teambuilder"])
logger = logging.getLogger("uvicorn")
LOCAL_MODEL = "qwen/qwen3.8-27b"

STOPWORDS = {
    "generame", "genera", "un", "equipo", "de", "con", "en", "para", "el", "la",
    "los", "las", "hazme", "armame", "quiero", "crea", "hacer", "modo", "set",
    "team", "porfa", "favor", "bueno", "competitivo", "ofensivo", "defensivo",
    "rapido", "lento", "balance", "trick", "room", "espacio", "raro", "lluvia",
    "sol", "arena", "nieve", "rain", "sun", "sand", "snow", "tailwind", "viento",
    "afin", "core", "forma", "lead", "pivot", "fast", "slow", "goodstuffs", "z"
}


def build_pokemon_family_index() -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """
    Construye un índice bidireccional de familias de Pokémon.
    Mapea tanto 'megagarchomp' como 'garchompmega', formas regionales y especies base.
    """
    pokedex_service._load_compendium_files()
    cache = pokedex_service._POKEDEX_CACHE

    family_map: Dict[str, List[str]] = {}
    canonical_display: Dict[str, str] = {}

    for clean_id, p_data in cache.items():
        full_name = p_data.get("name", "")
        if not full_name:
            continue

        clean_full = re.sub(r"[^a-z0-9]", "", full_name.lower())
        canonical_display[clean_full] = full_name

        # Especie base (ej. 'Garchomp' para 'Garchomp-Mega')
        base_species = p_data.get("baseSpecies") or full_name
        clean_base = re.sub(r"[^a-z0-9]", "", base_species.lower())

        if clean_base == clean_full:
            stripped = re.sub(
                r"(therian|alola|galar|hisui|paldea|wash|heat|frost|fan|mow|mega[xy]?|origin|crowned|shadow|ice|rapidstrike|singlestrike|bloodmoon|hearthflame|wellspring|cornerstone)$",
                "",
                clean_full,
            )
            if stripped and stripped != clean_full:
                clean_base = stripped

        # Variaciones de prefijo/sufijo para Megas (ej. 'megagarchomp' <-> 'garchompmega')
        variations = [clean_full, clean_base]
        if "mega" in clean_full:
            variations.append("mega" + clean_base)
            variations.append(clean_base + "mega")

        for var_key in variations:
            if var_key not in family_map:
                family_map[var_key] = []
            if full_name not in family_map[var_key]:
                family_map[var_key].append(full_name)

    return family_map, canonical_display


_NEG = {"sin", "no", "without", "sans", "pas", "nunca", "never", "not"}


def _asked(pattern: str, text: str) -> bool:
    """True si el pedido menciona el concepto y no está negado ('sin megas', 'no tera', 'sans méga')."""
    for m in re.finditer(pattern, text):
        prev = re.findall(r"[a-z]+", text[: m.start()])[-2:]
        if not (set(prev) & _NEG):
            return True
    return False


def autocorrect_and_validate_intent(
    user_prompt: str,
    format_name: str,
    mechanics: Dict[str, Any],
    legal_pokes: Dict[str, Any],
    lang: str = "es",
) -> List[str]:
    """
    Valida mecánicas (es/en/fr) y detecta Pokémon solicitados mediante autocorrector.
    Rechaza solicitudes si el Pokémon solicitado no es legal en este formato.
    """
    prompt_lower = norm_text(user_prompt)

    def refuse(key: str) -> None:
        raise HTTPException(status_code=400, detail=msg(key, lang, f=format_name))

    # 1. Validación de mecánicas
    if not mechanics.get("allow_megas", False) and _asked(r"\bmegas?\b|\bmegaevol\w*|\bmega-", prompt_lower):
        refuse("no_mega")
    if not mechanics.get("allow_tera", True) and mechanics.get("gen", 9) == 9 and \
            _asked(r"\btera(?:cristal\w*|stal\w*|crist\w*|tipo|type)?\b", prompt_lower):
        refuse("no_tera")
    if not mechanics.get("allow_z_moves", False) and \
            _asked(r"\bz[- ]?(?:moves?|crystals?)\b|\bmovimientos?[- ]?z\b|\bcristal(?:es)?[- ]?z\b|\bcapacites?[- ]?z\b|\bcristal[- ]?z\b", prompt_lower):
        refuse("no_z")
    if not mechanics.get("allow_dynamax", False) and _asked(r"\b(?:dinamax|dynamax|gigamax|gigantamax)\b", prompt_lower):
        refuse("no_dyna")

    # 2. Indexación de Pokémon legales en el formato actual
    legal_clean_keys: Set[str] = set()
    for k, v in legal_pokes.items():
        legal_clean_keys.add(re.sub(r"[^a-z0-9]", "", str(k).lower()))
        if isinstance(v, dict) and "name" in v:
            legal_clean_keys.add(re.sub(r"[^a-z0-9]", "", str(v["name"]).lower()))

    from src.services import pokedex_service as _pds
    _pds._load_compendium_files()
    entries, illegal = resolve_requests(prompt_lower, _pds._POKEDEX_CACHE, legal_pokes)
    if illegal:
        names = ", ".join(f"'{n}'" for n in dict.fromkeys(illegal))
        raise HTTPException(status_code=400, detail=msg("illegal_pokemon", lang, f=format_name, n=names))
    return [e.get("name") for e in entries]


@router.get("/formats")
async def list_formats():
    return {"formats": get_official_formats_list()}


@router.get("/format-pool/{format_id}")
async def get_format_pool_summary(format_id: str):
    pool = await filter_available_pool_for_format(format_id)
    legal_pokes = pool["legal_pokemon"]
    megas = [p["name"] for p in legal_pokes.values() if p.get("is_mega")]
    return {
        "format": pool["format"],
        "mechanics": pool["mechanics"],
        "total_legal_pokemon": len(legal_pokes),
        "total_legal_items": len(pool["legal_items"]),
        "total_legal_moves": len(pool["legal_moves"]),
        "available_megas": megas[:40],
    }


def _describe_ai_error(e: Exception, lang: str = "es") -> str:
    if isinstance(e, RateLimitError):
        return msg("ai_rate", lang)
    if isinstance(e, APIConnectionError):
        return msg("ai_conn", lang)
    if isinstance(e, APIStatusError):
        return msg("ai_status", lang, n=e.status_code)
    if isinstance(e, json.JSONDecodeError):
        return msg("ai_json", lang)
    return f"{type(e).__name__}: {e}"


def _ai_http_error(e: Exception, lang: str = "es") -> HTTPException:
    return HTTPException(status_code=429 if isinstance(e, RateLimitError) else 502, detail=_describe_ai_error(e, lang))


@router.post("/generate-team")
async def generate_team(req: TeamGenerationRequest):
    return JSONResponse(content=await build_team_response(format_id, prompt, lang))


def _nid(x: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


def make_strategy_guide(final_team: List[Dict[str, Any]], pool: Dict[str, Any], meta_pool: List[Dict[str, Any]],
                        era: Any, intent: Dict[str, Any], prompt: str, lang: str) -> Dict[str, Any]:
    """Guía táctica verificada (núcleo, apertura, victoria, amenazas). La usan el creador y el analizador."""
    team_abilities = {p.get("ability") for p in final_team if isinstance(p, dict) and p.get("ability")}
    team_moves = {m for p in final_team if isinstance(p, dict) for m in p.get("moves", [])}

    if intent["wants_perish_trap"]:
        real_archetype = "Perish Trap"
    elif intent["wants_tr"]:
        real_archetype = "Trick Room Offense"
    elif intent["wants_rain"]:
        real_archetype = "Rain Offense"
    elif intent["wants_sun"]:
        real_archetype = "Sun Offense"
    elif intent["wants_sand"]:
        real_archetype = "Sand Offense"
    elif "Trick Room" in team_moves:
        real_archetype = "Trick Room Offense"
    elif "Drizzle" in team_abilities:
        real_archetype = "Rain Offense"
    elif team_abilities & {"Drought", "Orichalcum Pulse"}:
        real_archetype = "Sun Offense"
    elif "Sand Stream" in team_abilities:
        real_archetype = "Sand Offense"
    elif "Tailwind" in team_moves:
        real_archetype = "Tailwind Offense"
    else:
        real_archetype = "Balanced Offense"

    team_species_set = {p.get("species") or p.get("name") for p in final_team if isinstance(p, dict)}
    threat_entries = [p for p in meta_pool if isinstance(p, dict) and p.get("name") not in team_species_set][:4]

    briefing_text, core_fallback, lead_fallback, threats_fallback = build_verified_tactical_briefing(
        final_team=final_team,
        threat_entries=threat_entries,
        pool=pool,
        era=era,
    )

    real_megas = [
        p.get("species", "") for p in final_team
        if isinstance(p, dict) and ("Mega" in p.get("species", "") or "-Mega" in p.get("species", ""))
    ]
    mega_guardrail = f"La ÚNICA Mega en este equipo es: {', '.join(real_megas)}." if real_megas else "Este equipo NO tiene Megas."

    # La guía es opcional: si la IA falla, responde cortada (max_tokens) o devuelve un JSON
    # inválido, el equipo ya está construido y se entrega una guía mínima generada por el motor.
    guide_data: Dict[str, Any] = {}
    guide_error = ""
    try:
        guide_resp = ai_client.chat.completions.create(
            model=LOCAL_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_TACTICIAN_PROMPT.format(
                        format_name=pool["format"]["name"],
                        archetype=real_archetype,
                        user_request=prompt.strip(),
                        era_rules=guide_era_rules(era),
                        verified_tactical_facts=f"{briefing_text}\n\nREGLA: {mega_guardrail} PROHIBIDO inventar que otro Pokémon es Mega.",
                    ) + language_rule(lang),
                },
                {
                    "role": "user",
                    "content": f"Solicitud: {prompt}\nIMPORTANTE: devuelve las 4 claves core, leads, win_condition y threats, de 2 a 3 frases cada una.",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        guide_text = guide_resp.choices[0].message.content.strip()
        parsed = json.loads(re.sub(r"^```(?:json)?\n|\n```$", "", guide_text))
        if isinstance(parsed, dict):
            guide_data = parsed
    except Exception as guide_err:
        guide_error = _describe_ai_error(guide_err, lang)
        logger.warning(f"Guía táctica de IA no disponible: {guide_error}")

    def _txt(v: Any) -> str:
        if isinstance(v, list):
            v = " ".join(str(x) for x in v)
        return re.sub(r"\s+", " ", str(v or "")).strip()

    def _trim(text: str, max_chars: int = 440) -> str:
        out, total = [], 0
        for s in sentences(text)[:3]:
            if out and total + len(s) > max_chars:
                break
            out.append(s)
            total += len(s) + 1
        return " ".join(out)

    legacy = guide_data.get("bullets") if isinstance(guide_data.get("bullets"), list) else []
    sections = []
    for idx, key in enumerate(("core", "leads", "win_condition", "threats")):
        raw = _txt(guide_data.get(key)) or (_txt(legacy[idx]) if idx < len(legacy) else "")
        # Coherencia: sin "pivotea" sin pivote en el set y sin conceptos que no existen en la era del formato
        clean = _trim(drop_era_anachronisms(drop_false_pivot_sentences(raw, final_team), era)) if raw else ""
        if clean:
            sections.append({"key": key, "text": clean})

    if sections:
        bullets = [s["text"] for s in sections]
        strategy_guide = {
            "format_name": pool["format"]["name"],
            "gameplay_mode": real_archetype,
            "sections": sections,
            "bullets": bullets,
            "core_concept": bullets[0],
            "turn_by_turn_plan": " ".join(bullets[1:3]),
            "threats_to_watch": [],
        }
    else:
        # Sin plantillas de respaldo: se informa el motivo real en la interfaz
        strategy_guide = {"error": guide_error or msg("guide_empty", lang)}
    return strategy_guide


async def build_team_response(
    format_id: str,
    prompt: str,
    lang: str = "es",
    keep: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    splice: Optional[Callable[[List[Dict[str, Any]]], Tuple[List[Dict[str, Any]], List[int]]]] = None,
    force_mega: bool = True,
    reserved_items: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    lang = norm_lang(lang)
    if not prompt or len(prompt.strip()) < 3:
        raise HTTPException(status_code=400, detail=msg("too_short", lang))
    if looks_off_topic(prompt):
        raise HTTPException(status_code=400, detail=msg("offtopic", lang))

    logger.info(f"==> Solicitud recibida para: {format_id} | Prompt: '{prompt}'")

    await ensure_showdown_descriptions_loaded()
    pool = await filter_available_pool_for_format(format_id)
    if not force_mega:  # al editar un equipo no se imponen cambios que el usuario no pidió
        pool = {**pool, "mechanics": {**pool["mechanics"], "force_mega": False}}
    # Cambios en conversación: los Pokémon retirados no pueden volver a elegirse en ningún paso
    excl = {_nid(x) for x in (exclude or []) if x}
    if excl:
        pool = {**pool, "legal_pokemon": {k: v for k, v in pool["legal_pokemon"].items()
                                          if _nid(k) not in excl and _nid(v.get("name", "")) not in excl}}

    # 1. Validación temprana y resolución inteligente
    requested_legal_pokemon = autocorrect_and_validate_intent(
        user_prompt=prompt,
        format_name=pool["format"]["name"],
        mechanics=pool["mechanics"],
        legal_pokes=pool["legal_pokemon"],
        lang=lang,
    )

    for k_name in keep or []:  # Pokémon que se quedan: obligatorios en el nuevo equipo
        if k_name and _nid(k_name) not in {_nid(x) for x in requested_legal_pokemon} and _nid(k_name) not in excl:
            requested_legal_pokemon.append(k_name)

    live_chaos = await fetch_live_format_chaos(format_id)
    smogon_sets = await fetch_smogon_sets(format_id)
    intent = parse_tactical_intent(prompt)

    filtered_context, requested_pokes, meta_pool = build_versatile_context_for_ai(
        pool=pool,
        live_chaos=live_chaos,
        user_prompt=prompt,
    )

    # Aseguramos que los Pokémon resueltos se inserten como OBJETOS DICT (evita error de string indices)
    for p_name in requested_legal_pokemon:
        clean_target = re.sub(r"[^a-z0-9]", "", p_name.lower())
        target_obj = None

        for k, v in pool.get("legal_pokemon", {}).items():
            if isinstance(v, dict):
                obj_name_clean = re.sub(r"[^a-z0-9]", "", v.get("name", "").lower())
                obj_id_clean = re.sub(r"[^a-z0-9]", "", str(v.get("id", "")).lower())
                if clean_target in (obj_name_clean, obj_id_clean, re.sub(r"[^a-z0-9]", "", str(k).lower())):
                    target_obj = v
                    break

        if target_obj:
            already_in = any(
                isinstance(rp, dict) and (rp.get("name") == target_obj.get("name") or rp.get("id") == target_obj.get("id"))
                for rp in requested_pokes
            )
            if not already_in:
                requested_pokes.append(target_obj)

    try:
        gen = int(pool["mechanics"].get("gen", 9) or 9)
        era = era_mechanics(gen)
        max_dex = MAX_DEX_BY_GEN.get(gen, 9999)
        legal_map = pool.get("legal_pokemon", {})
        base_names = sorted({
            (v.get("baseSpecies") or v.get("name")) for v in legal_map.values() if isinstance(v, dict) and v.get("name")
        })
        required_names = [rp.get("name") for rp in requested_pokes if isinstance(rp, dict) and rp.get("name")]
        required_block = (
            "POKÉMON OBLIGATORIOS (deben estar en selected_species, con esta forma exacta): " + ", ".join(required_names)
            if required_names else
            "No se nombraron Pokémon concretos: elige tú el equipo, pero SOLO con especies legales de este formato."
        )
        if excl:
            required_block += "\nPOKÉMON PROHIBIDOS (el usuario los retiró, NO los elijas): " + ", ".join(exclude)
        selector_system = SYSTEM_TEAM_SELECTOR_PROMPT.format(
            user_request=prompt.strip(),
            required_block=required_block,
            era_block=describe_era(gen, max_dex, base_names if len(base_names) <= 420 else None),
            format_filtered_context=filtered_context,
        )

        def _ask_selector(extra: str = "") -> List[str]:
            resp = ai_client.chat.completions.create(
                model=LOCAL_MODEL,
                messages=[
                    {"role": "system", "content": selector_system + f"\nWrite \"error_message\" in {LANGUAGE_NAMES[lang]}."},
                    {"role": "user", "content": f"Solicitud: {prompt.strip()}{extra}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            data = json.loads(re.sub(r"^```(?:json)?\n|\n```$", "", resp.choices[0].message.content.strip()))
            
            # --- PUERTA DE ESCAPE: Rechazo educado de la IA ---
            if isinstance(data, dict) and data.get("error_message"):
                raise HTTPException(status_code=400, detail=data["error_message"])

            raw = data.get("selected_species", []) if isinstance(data, dict) else data
            if isinstance(raw, str):
                raw = [s.strip() for s in raw.split(",") if s.strip()]
            return [str(x) for x in raw if _nid(x) not in excl] if isinstance(raw, list) else []

        from src.services import pokedex_service as _pds
        _pds._load_compendium_files()

        def _invalid(names: List[str]) -> List[str]:
            return [n for n in names if not resolve_species_name(n, _pds._POKEDEX_CACHE, legal_map)]

        ai_species = _ask_selector() if len(required_names) < 6 else []
        bad = _invalid(ai_species)
        if bad:
            ai_species = _ask_selector(
                f"\n\nERROR EN TU RESPUESTA ANTERIOR: estas especies NO existen o NO son legales en {pool['format']['name']} "
                f"(Pokédex válido #001–#{max_dex:03d}): {', '.join(bad)}. Reemplázalas por especies válidas "
                "y responde el JSON completo."
            )
            bad = _invalid(ai_species)
            if bad:
                raise HTTPException(
                    status_code=422,
                    detail=msg("species_invalid", lang, f=pool["format"]["name"], n=", ".join(bad)),
                )

        final_team = build_balanced_synergistic_team(
            ai_species_list=ai_species,
            requested_pokes=requested_pokes,
            meta_pool=meta_pool,
            pool=pool,
            live_chaos=live_chaos,
            smogon_sets=smogon_sets,
            user_prompt=prompt,
            reserved_items=reserved_items,
        )

        # Sin equipos "de relleno": el motor debe devolver integrantes completos
        if not final_team or any(not isinstance(p, dict) for p in final_team):
            raise HTTPException(status_code=500, detail=msg("engine_empty", lang))

        # Prioridad al pedido del usuario: todo Pokémon pedido (y legal) debe estar en el equipo
        def _base_key(s: Any) -> str:
            return re.sub(r"[^a-z0-9]", "", str(s).split("-")[0].lower())

        team_bases = {_base_key(p.get("species", "")) for p in final_team}
        missing = [rp.get("name") for rp in requested_pokes if isinstance(rp, dict) and _base_key(rp.get("name", "")) not in team_bases]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=msg("missing", lang, n=", ".join(repr(m) for m in missing)),
            )

        # Edición en conversación: se parte del equipo actual y solo cambia lo pedido
        rank = None
        if splice:
            final_team, rank = splice(final_team)

        # Última barrera: reglas del formato (movimientos, objetos, habilidades, cláusulas, límites)
        max_megas = 2 if (intent["wants_2_megas"] and pool["mechanics"].get("allow_megas")) else pool["mechanics"].get("max_megas", 0)
        try:
            final_team, notes = validate_team(
                final_team, pool, lambda n: resolve_species_name(n, _pds._POKEDEX_CACHE, legal_map), max_megas, lang, rank
            )
        except RuleViolation as rv:
            raise HTTPException(status_code=422, detail=str(rv))
        if pool["mechanics"].get("allow_dynamax") and final_team:
            best = max(final_team, key=lambda p: sum((p.get("base_stats") or {}).values()))
            notes.append(msg("dyna_pick", lang, s=best["species"]))

        strategy_guide = make_strategy_guide(final_team, pool, meta_pool, era, intent, prompt, lang)

        logger.info(f"==> ¡Equipo generado exitosamente: {[p.get('species') for p in final_team]}!")
        return {
            "format_id": format_id,
            "team": final_team,
            "strategy_guide": strategy_guide, "era": era, "generation": gen,
            "notes": notes, "lang": lang,
        }

    except HTTPException:
        raise
    except (RateLimitError, APIConnectionError, APIStatusError, json.JSONDecodeError) as e:
        logger.error(f"Fallo de IA en generación: {_describe_ai_error(e)}")
        raise _ai_http_error(e, lang)
    except Exception as e:
        logger.error(f"Fallo en generación: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar equipo: {str(e)}")