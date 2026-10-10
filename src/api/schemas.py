from typing import Dict, List, Optional
from pydantic import BaseModel


class TeamGenerationRequest(BaseModel):
    format_id: str
    prompt: str
    lang: str = "es"  # idioma de la interfaz: es | en | fr (solo afecta al texto redactado por la IA)


class PokemonSlot(BaseModel):
    species: str
    types: List[str]
    item: str
    ability: str
    tera_type: Optional[str] = None  # <-- Debe ser Optional para formatos sin Teracristal
    nature: str
    evs: Dict[str, int]
    moves: List[str]
    role: str
    sprite_url: Optional[str] = ""


class StrategyGuide(BaseModel):
    format_name: str
    core_concept: str
    gameplay_mode: str
    turn_by_turn_plan: str
    threats_to_watch: List[str]


class GeneratedTeamResponse(BaseModel):
    format_id: str
    team: List[PokemonSlot]
    strategy_guide: StrategyGuide

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    format_id: str
    messages: List[ChatMessage]          # historial; el último es el del usuario
    team: Optional[List[dict]] = None    # equipo actual (si existe) para poder modificarlo
    lang: str = "es"                     # idioma de la interfaz (se usa si no se detecta otro)
