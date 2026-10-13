from fastapi import APIRouter

from src.api.routes_analyzer import router as analyzer_router
from src.api.routes_chat import router as chat_router
from src.api.routes_pokedex import router as pokedex_router
from src.api.routes_teambuilder import router as teambuilder_router

router = APIRouter(prefix="/api")

router.include_router(teambuilder_router)
router.include_router(pokedex_router)
router.include_router(analyzer_router)
router.include_router(chat_router)
