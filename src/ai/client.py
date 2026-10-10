import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger("uvicorn")

# La clave se lee SOLO del entorno / del archivo .env de la raíz del proyecto (nunca del código).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_api_key = os.getenv("GROQ_API_KEY")
if not _api_key:
    logger.warning(
        "GROQ_API_KEY no está configurada: las funciones de IA (Creador y Analizador) fallarán. "
        "Crea un archivo .env en la raíz del proyecto con la línea GROQ_API_KEY=tu_clave"
    )

ai_client = OpenAI(
    api_key=_api_key or "GROQ_API_KEY-no-configurada",
    base_url="https://api.groq.com/openai/v1",
)

# Tope de tokens de SALIDA por llamada. Groq limita los tokens de salida por minuto (OTPM) y
# devuelve 429 al superarlos: con este tope ninguna llamada puede consumir más de 900.
MAX_OUTPUT_TOKENS = 900
