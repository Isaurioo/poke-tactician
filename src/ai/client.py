import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger("uvicorn")

# La clave se lee SOLO del entorno / del archivo .env de la raíz del proyecto (nunca del código).
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

_gemini_key = os.getenv("GEMINI_API_KEY")
_groq_key = os.getenv("GROQ_API_KEY")

# Si se configuró GEMINI_API_KEY o si el usuario pegó la clave de Google en GROQ_API_KEY (empieza con AIzaSy)
if _gemini_key or (_groq_key and _groq_key.startswith("AIzaSy")):
    _api_key = _gemini_key or _groq_key
    _base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    _provider = "gemini"
    LOCAL_MODEL = os.getenv("AI_MODEL", "gemini-3.5-flash-lite")
    FALLBACK_MODELS = [
        LOCAL_MODEL,
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash",
    ]
else:
    _api_key = _groq_key or "NO_API_KEY"
    _base_url = "https://api.groq.com/openai/v1"
    _provider = "groq"
    LOCAL_MODEL = os.getenv("AI_MODEL", "qwen/qwen3.8-27b")
    FALLBACK_MODELS = [LOCAL_MODEL]

# Alias públicos para módulos que necesitan hablar con el proveedor directamente (p. ej. búsqueda web con grounding)
AI_PROVIDER = _provider
AI_API_KEY = _api_key

logger.info(f"AI Provider configurado: {_provider} (modelo: {LOCAL_MODEL})")

ai_client = OpenAI(
    api_key=_api_key,
    base_url=_base_url,
)

# Envoltura resiliente: si un modelo da 429 (cuota de modelo agotada) o 503 (saturación),
# prueba automáticamente el siguiente modelo de fallback sin fallar la petición.
_orig_chat_create = ai_client.chat.completions.create


def _resilient_chat_create(**kwargs):
    requested_model = kwargs.get("model", LOCAL_MODEL)
    models_to_try = [requested_model]
    for m in FALLBACK_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    last_error = None
    for idx, model_name in enumerate(models_to_try):
        call_kwargs = dict(kwargs)
        call_kwargs["model"] = model_name
        try:
            return _orig_chat_create(**call_kwargs)
        except Exception as e:
            from openai import APIStatusError, RateLimitError
            status = getattr(e, "status_code", 429 if isinstance(e, RateLimitError) else None)
            if status in (429, 503) and idx < len(models_to_try) - 1:
                next_model = models_to_try[idx + 1]
                logger.warning(
                    f"AI modelo '{model_name}' reportó HTTP {status}. "
                    f"Cambiando automáticamente a modelo de respaldo: '{next_model}'..."
                )
                last_error = e
                continue
            raise

    if last_error:
        raise last_error


ai_client.chat.completions.create = _resilient_chat_create

MAX_OUTPUT_TOKENS = 3500 if _provider == "gemini" else 1200
IS_GEMINI = (_provider == "gemini")


def get_reasoning_kwargs(effort: str = "low") -> dict:
    """Controla el presupuesto de pensamiento de la IA para acelerar respuestas preservando la calidad táctica."""
    if _provider == "gemini":
        return {"reasoning_effort": effort}
    return {}

