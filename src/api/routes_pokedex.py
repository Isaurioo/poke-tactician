from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from src.services.pokedex_service import (
    describe_terms,
    get_ability_detail,
    get_compendium_overview,
    get_item_detail,
    get_item_icon_map,
    get_l10n,
    get_move_detail,
    get_pokemon_detail,
)

router = APIRouter(prefix="", tags=["Pokédex"])


@router.get("/compendium")
async def compendium_overview_endpoint():
    return JSONResponse(content=get_compendium_overview())


@router.get("/compendium/item-icons")
async def item_icons_endpoint():
    """Mapa {id_objeto: spritenum} para dibujar iconos 2D de objetos en cualquier vista."""
    return JSONResponse(content=get_item_icon_map())


class DescribeRequest(BaseModel):
    abilities: List[str] = []
    items: List[str] = []
    moves: List[str] = []


@router.post("/compendium/describe")
async def describe_endpoint(req: DescribeRequest):
    """Descripciones localizables de los términos de un equipo (habilidades, objetos, movimientos)."""
    return JSONResponse(content=describe_terms(req.abilities[:60], req.items[:60], req.moves[:120]))


@router.get("/compendium/l10n/{lang}")
async def l10n_endpoint(lang: str):
    """Nombres y descripciones traducidos (es / fr) indexados por id."""
    return JSONResponse(content=get_l10n(lang))


@router.get("/compendium/pokemon/{name}")
async def pokemon_detail_endpoint(name: str):
    detail = get_pokemon_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail="Pokémon no encontrado.")
    return JSONResponse(content=detail)


@router.get("/compendium/move/{name}")
async def move_detail_endpoint(name: str):
    detail = get_move_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado.")
    return JSONResponse(content=detail)


@router.get("/compendium/item/{name}")
async def item_detail_endpoint(name: str):
    detail = get_item_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail="Objeto no encontrado.")
    return JSONResponse(content=detail)


@router.get("/compendium/ability/{name}")
async def ability_detail_endpoint(name: str):
    detail = get_ability_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail="Habilidad no encontrada.")
    return JSONResponse(content=detail)
