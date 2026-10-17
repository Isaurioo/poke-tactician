"""Búsqueda web en vivo de equipos de referencia ("campeón del mundial de X", "Big 6 de VGC 2016", un jugador, un arquetipo...).

La IA del proveedor configurado hace la búsqueda con su herramienta nativa y devuelve un roster con fuentes:
  - Gemini: API nativa generateContent con la herramienta `google_search` (grounding).
  - Groq:   modelos "compound" (búsqueda web integrada) por la API compatible con OpenAI.
El resultado SIEMPRE se valida después contra el formato elegido (reference_teams.fit_roster); aquí no se relaja ninguna regla.
Cualquier fallo (sin clave, cuota, modelo sin búsqueda, JSON ilegible, timeout) devuelve None y el flujo cae a las demás fuentes.
"""
import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.ai import client as ai
from src.ai.prompts import SYSTEM_WEB_TEAM_PROMPT

logger = logging.getLogger("uvicorn")

WEB_TIMEOUT_S = float(os.getenv("WEB_LOOKUP_TIMEOUT", "45"))
CACHE_TTL_S = 24 * 3600
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
LAST_ERROR: str = ""  # motivo del último fallo (se muestra en las notas para poder diagnosticar)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Modelos con búsqueda: primero el configurado por el usuario, luego los de respaldo del proyecto.
GEMINI_SEARCH_MODELS = [m for m in [os.getenv("AI_SEARCH_MODEL"), *getattr(ai, "FALLBACK_MODELS", [])] if m]
GROQ_SEARCH_MODEL = os.getenv("AI_SEARCH_MODEL", "groq/compound-mini")


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Primer objeto JSON del texto (tolera ```json y texto alrededor)."""
    if not text:
        return None
    t = re.sub(r"```(?:json)?", "", text).strip()
    start = t.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            depth += t[i] == "{"
            depth -= t[i] == "}"
            if depth == 0:
                try:
                    data = json.loads(t[start:i + 1])
                    return data if isinstance(data, dict) else None
                except Exception:
                    break
        start = t.find("{", start + 1)
    return None


def normalize_result(data: Optional[Dict[str, Any]], grounded_urls: List[str]) -> Optional[Dict[str, Any]]:
    """Valida la forma de la respuesta del modelo. Devuelve None si no hay un equipo utilizable."""
    if not isinstance(data, dict) or not data.get("found"):
        return None
    if str(data.get("confidence", "")).lower() == "low":
        return None
    raw = data.get("species")
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    if not isinstance(raw, list):
        return None
    species = [str(x).strip() for x in raw if str(x).strip()][:6]
    if len(species) < 3:
        return None
    urls = [u for u in (data.get("sources") or []) if isinstance(u, str) and u.startswith("http")]
    for u in grounded_urls:
        if u not in urls:
            urls.append(u)
    return {
        "source": str(data.get("source") or "equipo encontrado en la web")[:140],
        "definition": str(data.get("definition") or "")[:240],
        "exact": bool(data.get("exact")) and len(species) >= 6,
        "sources": urls[:4],
        "species": species,
    }


async def _gemini_search(system: str, user: str) -> Tuple[str, List[str]]:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.0},
    }
    headers = {"x-goog-api-key": ai.AI_API_KEY, "Content-Type": "application/json"}
    last_err: Optional[str] = None
    async with httpx.AsyncClient(timeout=WEB_TIMEOUT_S) as client:
        for model in dict.fromkeys(GEMINI_SEARCH_MODELS):
            try:
                r = await client.post(GEMINI_URL.format(model=model), headers=headers, json=body)
            except Exception as err:
                last_err = f"{model}: {err}"
                continue
            if r.status_code != 200:
                last_err = f"{model}: HTTP {r.status_code}"
                logger.warning(f"Búsqueda web {model} -> HTTP {r.status_code}: {r.text[:300]}")
                continue  # 400 = el modelo no admite búsqueda; 429/503 = cuota o saturación: prueba el siguiente
            data = r.json()
            cand = (data.get("candidates") or [{}])[0]
            text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
            chunks = (cand.get("groundingMetadata") or {}).get("groundingChunks", []) or []
            urls = [c["web"]["uri"] for c in chunks if isinstance(c.get("web"), dict) and c["web"].get("uri")]
            if text.strip():
                return text, urls
            last_err = f"{model}: respuesta vacía"
    raise RuntimeError(last_err or "sin modelos de búsqueda disponibles")


def _groq_search_sync(system: str, user: str) -> str:
    resp = ai.ai_client.chat.completions.create(
        model=GROQ_SEARCH_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0,
    )
    return resp.choices[0].message.content or ""


async def web_lookup_team(prompt: str, pool: Dict[str, Any], bring_n: int) -> Optional[Dict[str, Any]]:
    """Busca en la web el equipo pedido. Devuelve {'source','definition','exact','sources','species'} o None
    (el motivo queda en LAST_ERROR)."""
    global LAST_ERROR
    LAST_ERROR = ""
    fmt = pool["format"]
    norm_prompt = re.sub(r"\s+", " ", prompt.lower()).strip()
    key = f"{fmt.get('id', '')}|{norm_prompt}"
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1]

    rule_txt = f"se llevan {bring_n} de 6" if bring_n < 6 else "se usan los 6 Pokémon"
    system = SYSTEM_WEB_TEAM_PROMPT.format(user_request=prompt.strip(), format_name=fmt["name"], bring_rule=rule_txt)
    user = f"Busca en la web y responde en JSON: {prompt.strip()} (formato: {fmt['name']})"
    try:
        if ai.AI_PROVIDER == "gemini":
            text, urls = await asyncio.wait_for(_gemini_search(system, user), timeout=WEB_TIMEOUT_S + 30)
        else:
            text = await asyncio.wait_for(asyncio.to_thread(_groq_search_sync, system, user), timeout=WEB_TIMEOUT_S + 10)
            urls = []
    except Exception as err:
        LAST_ERROR = (str(err) or err.__class__.__name__)[:160]
        logger.warning(f"Búsqueda web de equipo no disponible: {LAST_ERROR}")
        return None

    parsed = extract_json(text)
    result = normalize_result(parsed, urls)
    if result:
        _CACHE[key] = (time.time(), result)
    else:
        LAST_ERROR = "la búsqueda no encontró el equipo con claridad" if parsed is not None else "respuesta sin JSON válido"
        logger.info(f"Búsqueda web sin resultado utilizable: {LAST_ERROR}")
    return result
