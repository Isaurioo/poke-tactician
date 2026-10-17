import difflib
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.ai.client import LOCAL_MODEL, MAX_OUTPUT_TOKENS, ai_client, get_reasoning_kwargs
from openai import APIConnectionError, APIStatusError, RateLimitError
from src.core.entity_extraction import norm_text, resolve_requests, resolve_species_name
from src.core.archetypes import (assign_tera_types, check_request, enforce_features, mark_dynamax, mark_primal, strip_gmax,
                                 team_archetype, verify_outcome)
from src.core.messages import msg, norm_lang
from src.core.team_validator import RuleViolation, validate_team
from src.core.topic_guard import looks_off_topic
from src.core.era_rules import describe_era, era_mechanics, guide_era_rules
from src.core.move_rules import PROTECT_FAMILY, norm_move
from src.services.format_engine import MAX_DEX_BY_GEN
from src.core.text_validator import drop_era_anachronisms, drop_false_pivot_sentences, sentences
from src.ai.prompts import (LANGUAGE_NAMES, SYSTEM_REFERENCE_TEAM_PROMPT, SYSTEM_TACTICIAN_PROMPT,
                            SYSTEM_TEAM_SELECTOR_PROMPT, language_rule, mega_rule_text)
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
    mega_rule_limit,
    parse_tactical_intent,
    picked_team_size,
)
from src.services import web_lookup
from src.services.reference_teams import fetch_paste_sets, pseudo_stats_from_sets, resolve_reference_team
from src.services.web_lookup import web_lookup_team

router = APIRouter(prefix="", tags=["Teambuilder"])
logger = logging.getLogger("uvicorn")

STOPWORDS = {
    "generame", "genera", "un", "equipo", "de", "con", "en", "para", "el", "la",
    "los", "las", "hazme", "armame", "quiero", "crea", "hacer", "modo", "set",
    "team", "porfa", "favor", "bueno", "competitivo", "ofensivo", "defensivo",
    "rapido", "lento", "balance", "trick", "room", "espacio", "raro", "lluvia",
    "sol", "arena", "nieve", "rain", "sun", "sand", "snow", "tailwind", "viento",
    "afin", "core", "forma", "lead", "pivot", "fast", "slow", "goodstuffs", "z"
}


def _parse_json(text: str) -> Dict[str, Any]:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    text = re.sub(r"<thought>.*?</thought>", "", text or "", flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    m = re.search(r"\{.*\}", text, flags=re.S)
    target = m.group(0) if m else text
    try:
        return json.loads(target)
    except json.JSONDecodeError as err:
        logger.error(f"Fallo al decodificar JSON de IA: {err}. Contenido recibido: {text[:400]}")
        raise


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
    raw_prompt: Optional[str] = None,
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
    if not mechanics.get("allow_tera", True) and \
            _asked(r"\btera(?:cristal\w*|stal\w*|crist\w*|tipo|type)?\b", prompt_lower):
        refuse("no_tera")
    if not mechanics.get("allow_z_moves", False) and \
            _asked(r"\bz[- ]?(?:moves?|crystals?)\b|\bmovimientos?[- ]?z\b|\bcristal(?:es)?[- ]?z\b|\bcapacites?[- ]?z\b|\bcristal[- ]?z\b|\bcristaux[- ]?z\b", prompt_lower):
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

    # Si se proporcionó raw_prompt (el mensaje directo del usuario sin alucinaciones de IA),
    # solo consideramos ilegales aquellos Pokémon que el usuario nombró explícitamente en su mensaje.
    if raw_prompt and illegal:
        _, raw_illegal = resolve_requests(norm_text(raw_prompt), _pds._POKEDEX_CACHE, legal_pokes)
        raw_illegal_keys = {re.sub(r"[^a-z0-9]", "", str(x).lower()) for x in raw_illegal}
        illegal = [n for n in illegal if re.sub(r"[^a-z0-9]", "", str(n).lower()) in raw_illegal_keys]

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
        err_msg = str(getattr(e, "body", "") or getattr(e, "message", "") or str(e)).lower()
        if any(w in err_msg for w in ["generaterequestsperday", "daily", "free_tier_requests", "retry in"]):
            if lang == "es":
                return "La IA agotó la cuota diaria del modelo actual. Se ha activado el sistema de respaldo automático o puedes cambiar de modelo en .env."
            elif lang == "fr":
                return "L'IA a atteint son quota quotidien gratuit pour ce modèle."
            else:
                return "The AI reached the free daily quota for this model."
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
    return JSONResponse(content=await build_team_response(req.format_id, req.prompt, req.lang or "es"))


def _nid(x: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


def _assemble_guide(format_name: str, mode: str, texts: Dict[str, str]) -> Dict[str, Any]:
    """Estructura única de guía táctica: `sections` (render principal) + claves legacy (core_concept, turn_by_turn_plan...).
    El frontend decide qué rama pintar según estas claves, así que TODAS las rutas (creación, edición por chat,
    analizador) deben devolverla completa para no dejar apartados en blanco."""
    sections = [{"key": k, "text": texts[k]} for k in ("core", "leads", "win_condition", "threats") if texts.get(k)]
    bullets = [s["text"] for s in sections]
    by_key = {s["key"]: s["text"] for s in sections}
    return {
        "format_name": format_name,
        "gameplay_mode": mode,
        "sections": sections,
        "bullets": bullets,
        "core_concept": by_key.get("core", ""),
        "turn_by_turn_plan": " ".join(x for x in (by_key.get("leads"), by_key.get("win_condition")) if x),
        "threats_to_watch": [by_key["threats"]] if by_key.get("threats") else [],
        # Alias con los nombres de las claves del prompt del LLM, por si otro consumidor los lee
        "core": by_key.get("core", ""),
        "leads": by_key.get("leads", ""),
        "win_condition": by_key.get("win_condition", ""),
        "threats": by_key.get("threats", ""),
        "verified": True,
    }


def _only_user_named(requested: List[Dict[str, Any]], raw_prompt: Optional[str], legal_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pedido de un equipo concreto (Big 6, campeón...): el chat reescribe el mensaje con un router de IA que puede INVENTAR
    Pokémon ("Big 6 team with Kangaskhan, ..., Rayquaza"). Solo cuentan como obligatorios los que el jugador escribió él mismo."""
    if not raw_prompt:
        return requested
    pokedex_service._load_compendium_files()
    named, _illegal = resolve_requests(norm_text(raw_prompt), pokedex_service._POKEDEX_CACHE, legal_map)
    named_bases = {_nid(e.get("baseSpecies") or e.get("name")) for e in named}
    return [rp for rp in requested
            if not isinstance(rp, dict) or _nid(rp.get("baseSpecies") or rp.get("name")) in named_bases]


def _primal_hint(pool: Dict[str, Any]) -> str:
    """Si el formato permite Groudon/Kyogre con sus orbes (Gen 6/7), se lo dice al selector."""
    gen = int(pool["mechanics"].get("gen", 9) or 9)
    items, legal = pool.get("legal_items", {}), pool.get("legal_pokemon", {})
    if gen in (6, 7) and "redorb" in items and "blueorb" in items and ("groudon" in legal or "kyogre" in legal):
        return (" Groudon y Kyogre (si los eliges) usan su Reversión Primigenia con la Orbe Roja/Azul: NO cuenta como Mega "
                "y cuenta como Pokémon restringido.")
    return ""


async def _recall_roster(prompt: str, pool: Dict[str, Any], bring_n: int) -> Optional[Dict[str, Any]]:
    """ÚLTIMO recurso: la IA recuerda un roster. No verificado; el motor lo valida y lo marca como tal."""
    fmt = pool["format"]
    rule_txt = (f"se llevan {bring_n} de 6" if bring_n < 6 else "se usan los 6 Pokémon")
    try:
        resp = ai_client.chat.completions.create(
            model=LOCAL_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_REFERENCE_TEAM_PROMPT.format(
                    user_request=prompt.strip(), format_name=fmt["name"], bring_rule=rule_txt)},
                {"role": "user", "content": f"Solicitud: {prompt.strip()}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=MAX_OUTPUT_TOKENS,
            **get_reasoning_kwargs("low"),
        )
        data = _parse_json(resp.choices[0].message.content or "")
    except (RateLimitError, APIConnectionError, APIStatusError):
        raise  # los errores de la IA ya se traducen a HTTP más arriba
    except Exception as err:  # JSON ilegible u otra falla: se cae al flujo normal, sin romper la generación
        logger.warning(f"Equipo de referencia no disponible: {err}")
        return None
    if not isinstance(data, dict) or not data.get("found") or str(data.get("confidence", "")).lower() == "low":
        return None
    raw = data.get("species")
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    if not isinstance(raw, list) or len(raw) < 4:
        return None
    return {"source": str(data.get("source") or "equipo de referencia")[:120], "species": [str(x) for x in raw[:6]]}


def make_strategy_guide(final_team: List[Dict[str, Any]], pool: Dict[str, Any], meta_pool: List[Dict[str, Any]],
                        era: Any, intent: Dict[str, Any], prompt: str, lang: str, skip_ai: bool = False,
                        bring_n: int = 6) -> Dict[str, Any]:
    """Guía táctica verificada (núcleo, apertura, victoria, amenazas). La usan el creador y el analizador."""
    team_abilities = {p.get("ability") for p in final_team if isinstance(p, dict) and p.get("ability")}
    team_moves = {m for p in final_team if isinstance(p, dict) for m in p.get("moves", [])}

    real_archetype = team_archetype(final_team, pool)  # sale del equipo final, no de lo que se pidió

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
    if len(real_megas) >= 2:
        mega_guardrail = (f"Las Megas de este equipo son: {', '.join(real_megas)}. Solo UNA evoluciona por combate y se eligen {bring_n} de 6: "
                          "en 'leads' indica con qué rivales conviene llevar cada Mega.")
    else:
        mega_guardrail = f"La ÚNICA Mega en este equipo es: {', '.join(real_megas)}." if real_megas else "Este equipo NO tiene Megas."

    if skip_ai:
        lead_poke = final_team[0].get("species", "tus atacantes") if final_team else "tus atacantes"
        win_msg = (
            f"Consolida el control de la partida posicionando a {lead_poke} y manteniendo la ventaja de daño."
            if lang == "es" else
            f"Consolidate board control by positioning {lead_poke} and maintaining damage pressure."
        )
        threats_txt = " ".join(threats_fallback) if isinstance(threats_fallback, list) else str(threats_fallback or "")
        guide = _assemble_guide(pool["format"]["name"], real_archetype, {
            "core": core_fallback, "leads": lead_fallback, "win_condition": win_msg, "threats": threats_txt,
        })
        guide["briefing"] = briefing_text
        return guide

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
            **get_reasoning_kwargs("low"),
        )
        guide_text = guide_resp.choices[0].message.content or ""
        parsed = _parse_json(guide_text)
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
        texts = {s["key"]: s["text"] for s in sections}
        lead_poke = final_team[0].get("species", "") if final_team else ""
        engine_fill = {
            "core": core_fallback,
            "leads": lead_fallback,
            "win_condition": (f"Consolida el control de la partida posicionando a {lead_poke} y manteniendo la ventaja de daño."
                              if lang == "es" else f"Consolidate board control by positioning {lead_poke} and maintaining damage pressure."),
            "threats": " ".join(threats_fallback) if isinstance(threats_fallback, list) else str(threats_fallback or ""),
        }
        for k, v in engine_fill.items():  # ningún apartado debe quedar vacío si el LLM omitió alguna clave
            texts.setdefault(k, v)
        strategy_guide = _assemble_guide(pool["format"]["name"], real_archetype, texts)
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
    raw_prompt: Optional[str] = None,
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

    # Exclusiones pedidas por el usuario ("sin legendarios", "sin paradojas") y viabilidad según la generación/formato
    intent0 = parse_tactical_intent(prompt)
    def _excluded(p: Dict[str, Any]) -> bool:
        return bool((intent0["no_legendary"] and (p.get("is_restricted") or p.get("is_sublegend") or p.get("is_mythical")))
                    or (intent0["no_mythical"] and p.get("is_mythical")) or (intent0["no_paradox"] and p.get("is_paradox")))
    if intent0["no_legendary"] or intent0["no_paradox"] or intent0["no_mythical"]:
        pool = {**pool, "legal_pokemon": {k: v for k, v in pool["legal_pokemon"].items() if not _excluded(v)}}
    plan_errors, plan_notes = check_request(intent0, pool, lang)
    if plan_errors:
        raise HTTPException(status_code=400, detail=" ".join(plan_errors))

    # 1. Validación temprana y resolución inteligente
    requested_legal_pokemon = autocorrect_and_validate_intent(
        user_prompt=prompt,
        format_name=pool["format"]["name"],
        mechanics=pool["mechanics"],
        legal_pokes=pool["legal_pokemon"],
        lang=lang,
        raw_prompt=raw_prompt,
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

    ref_notes: List[str] = []
    reference_mode = False
    try:
        gen = int(pool["mechanics"].get("gen", 9) or 9)
        era = era_mechanics(gen)
        bring_n = picked_team_size(pool)

        # --- Equipos de referencia (campeón, regional, Big 6, arquetipo con nombre) ---
        # Se pide el roster a la IA (o al uso real en el Big 6), y el MOTOR valida cada especie contra el formato.
        # El chat reescribe el pedido con un "router" de IA que puede perder palabras clave ("campeón del mundial 2024"):
        # la detección y la búsqueda usan TAMBIÉN el mensaje original del jugador.
        ref_query = raw_prompt or prompt
        ref_intent = parse_tactical_intent(ref_query) if raw_prompt else intent
        ref_flags = {**intent, **{k: bool(intent.get(k) or ref_intent.get(k)) for k in
                                   ("wants_reference_team", "wants_big6", "wants_generic_popular", "wants_popular")}}
        if ref_flags["wants_reference_team"] and not splice and not keep:
            requested_pokes = _only_user_named(requested_pokes, raw_prompt, pool["legal_pokemon"])
            ref = await resolve_reference_team(ref_query, ref_flags, pool, bring_n, mega_rule_limit(pool, intent), _recall_roster, web_lookup_team)
            if ref and ref["resolved"]:
                resolved, dropped, kind = ref["resolved"], ref["dropped"], ref["kind"]
                # Lo que el jugador nombró explícitamente va primero; el equipo de referencia completa hasta 6 sin duplicar especies.
                _bases = {_nid(rp.get("baseSpecies") or rp.get("name")) for rp in requested_pokes if isinstance(rp, dict)}
                for entry in resolved:
                    _b = _nid(entry.get("baseSpecies") or entry.get("name"))
                    if len(requested_pokes) < 6 and _b not in _bases:
                        requested_pokes.append(entry)
                        _bases.add(_b)
                reference_mode = len(resolved) >= 5 and len(requested_pokes) == len(resolved)
                logger.info(f"==> Equipo de referencia ({kind}, {ref.get('source')}): {[e.get('name') for e in resolved]}")
                fmt_name = pool["format"]["name"]
                meta = ref.get("usage_meta") or {}
                kept_real = len(resolved) - ref.get("filled", 0)
                if kind == "kb":
                    ref_notes.append(msg("ref_kb", lang, src=ref["source"], url=ref.get("url") or "-"))
                    if ref.get("origin_format"):
                        ref_notes.append(msg("ref_fmt_mismatch", lang, orig=ref["origin_format"], f=fmt_name, k=kept_real))
                    elif dropped:
                        ref_notes.append(msg("ref_partial", lang, src=ref["source"], f=fmt_name, k=kept_real, n=len(dropped)) + " (" + ", ".join(dropped) + ")")
                elif kind == "web":
                    w = ref.get("web") or {}
                    defn = f" {w['definition']}" if w.get("definition") else ""
                    ref_notes.append(msg("ref_web", lang, src=ref["source"], defn=defn, urls=ref.get("url") or "-",
                                         exact=msg("ref_web_exact" if w.get("exact") else "ref_web_approx", lang)))
                    if dropped:
                        ref_notes.append(msg("ref_partial", lang, src=ref["source"], f=fmt_name, k=kept_real, n=len(dropped)) + " (" + ", ".join(dropped) + ")")
                elif kind in ("big6", "usage"):
                    ref_notes.append(msg("ref_usage", lang, what=ref["source"], f=fmt_name, month=meta.get("month", "?"),
                                         rating=meta.get("rating", "?"),
                                         desc=msg("ref_big6_desc" if kind == "big6" else "ref_core_desc", lang)))
                else:  # recall: memoria del modelo, NO verificado
                    ref_notes.append(msg("ref_recall", lang, src=ref["source"]))
                    if dropped:
                        ref_notes.append(msg("ref_partial", lang, src=ref["source"], f=fmt_name, k=kept_real, n=len(dropped)) + " (" + ", ".join(dropped) + ")")
                if ref.get("web_failed"):
                    ref_notes.append(msg("ref_web_failed", lang, why=web_lookup.LAST_ERROR or "sin respuesta"))
                # Sets REALES del equipo si hay un Pokepaste (equipo verificado o fuente de la búsqueda web)
                if ref.get("paste_urls"):
                    _sets = await fetch_paste_sets(ref["paste_urls"])
                    pokedex_service._load_compendium_files()
                    _pseudo = pseudo_stats_from_sets(_sets, pool["legal_pokemon"], pokedex_service._POKEDEX_CACHE)
                    _roster = {_nid(e.get("name")) for e in resolved}
                    _match = {k: v for k, v in _pseudo.items() if k in _roster}
                    if len(_match) >= 4:
                        live_chaos = {**live_chaos, **_match}
                        ref_notes.append(msg("ref_paste", lang, url=ref["paste_urls"][0]))
                if ref.get("filled"):
                    ref_notes.append(msg("ref_filled", lang, n=ref["filled"], f=fmt_name))
            else:
                ref_notes.append(msg("ref_unverified", lang, q=ref_query.strip()[:80], f=pool["format"]["name"]))
                if web_lookup.LAST_ERROR:
                    ref_notes.append(msg("ref_web_failed", lang, why=web_lookup.LAST_ERROR))
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
        if intent0["no_legendary"] or intent0["no_mythical"]:
            required_block += "\nEL USUARIO NO QUIERE legendarios, restringidos ni míticos: no elijas ninguno."
        if intent0["no_paradox"]:
            required_block += "\nEL USUARIO NO QUIERE Pokémon paradoja: no elijas ninguno."
        if intent0.get("core_types"):
            required_block += "\nNÚCLEO DE TIPOS OBLIGATORIO: el equipo debe incluir al menos un Pokémon de cada tipo: " + ", ".join(intent0["core_types"]) + "."
        if excl:
            required_block += "\nPOKÉMON PROHIBIDOS (el usuario los retiró, NO los elijas): " + ", ".join(exclude)
        selector_system = SYSTEM_TEAM_SELECTOR_PROMPT.format(
            user_request=prompt.strip(),
            required_block=required_block,
            era_block=describe_era(gen, max_dex, base_names if len(base_names) <= 420 else None),
            format_filtered_context=filtered_context,
            mega_block=mega_rule_text(bool(pool["mechanics"].get("allow_megas")), mega_rule_limit(pool, intent0),
                                      bring_n, bool(intent0.get("wants_2_megas"))) + _primal_hint(pool),
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
                **get_reasoning_kwargs("low"),
            )
            content = resp.choices[0].message.content or ""
            data = _parse_json(content)
            
            # --- PUERTA DE ESCAPE: Rechazo educado de la IA ---
            if isinstance(data, dict) and data.get("error_message"):
                raise HTTPException(status_code=400, detail=data["error_message"])

            raw = data.get("selected_species", []) if isinstance(data, dict) else data
            if isinstance(raw, str):
                raw = [s.strip() for s in raw.split(",") if s.strip()]
            if not isinstance(raw, list):
                return []
            names, saw_gmax = strip_gmax([str(x) for x in raw])
            if saw_gmax:
                intent["wants_gmax"] = True  # el modelo quiso Gigamax: lo marca el motor, no el sufijo del nombre
            return [x for x in names if _nid(x) not in excl]

        from src.services import pokedex_service as _pds
        _pds._load_compendium_files()

        def _invalid(names: List[str]) -> List[str]:
            return [n for n in names if not resolve_species_name(n, _pds._POKEDEX_CACHE, legal_map)]

        # Al editar (splice), evitamos llamar al selector de la IA si no faltan especies (ahorra miles de tokens y previene 429)
        needs_ai_selector = (len(required_names) < 6) and (not splice) and (not keep or len(keep) < 6)
        ai_species = _ask_selector() if needs_ai_selector else []
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
            reference_mode=reference_mode,
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
        if not splice:
            enforce_features(final_team, intent, pool, lambda n: resolve_species_name(n, _pds._POKEDEX_CACHE, legal_map))
        rank = None
        if splice:
            final_team, rank = splice(final_team)

        # Última barrera: reglas del formato (movimientos, objetos, habilidades, cláusulas, límites)
        max_megas = mega_rule_limit(pool, intent)
        try:
            final_team, notes = validate_team(
                final_team, pool, lambda n: resolve_species_name(n, _pds._POKEDEX_CACHE, legal_map), max_megas, lang, rank
            )
        except RuleViolation as rv:
            raise HTTPException(status_code=422, detail=str(rv))
        mark_primal(final_team)
        notes += mark_dynamax(final_team, pool, bool(intent.get("wants_gmax")), lambda n: resolve_species_name(n, _pds._POKEDEX_CACHE, legal_map), lang)
        if not splice:
            notes += assign_tera_types(final_team, intent, pool, lang)

        team_megas = [p.get("species", "") for p in final_team if "Mega" in str(p.get("species", ""))]
        if len(team_megas) >= 2:
            notes.append(msg("mega_pair", lang, n=len(team_megas), m=", ".join(team_megas), b=bring_n))
        strategy_guide = make_strategy_guide(final_team, pool, meta_pool, era, intent, prompt, lang, skip_ai=bool(splice), bring_n=bring_n)
        if not splice:  # al editar no se juzga el equipo contra el pedido original
            notes = list(dict.fromkeys(ref_notes + plan_notes + notes + verify_outcome(intent, final_team, pool, lang)))

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