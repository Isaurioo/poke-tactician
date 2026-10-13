"""
Fuente única de verdad sobre qué existe en cada generación: formas, movimientos, objetos y aprendizajes.
Todo el motor (pool, generador, validador, analizador, chat y sugerencias) debe consultar este módulo.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Set

DATA = Path(__file__).resolve().parents[1] / "data"
_DEX_LAST = [(151, 1), (251, 2), (386, 3), (493, 4), (649, 5), (721, 6), (809, 7), (905, 8), (1025, 9)]
_MOVE_LAST = [(165, 1), (251, 2), (354, 3), (467, 4), (559, 5), (621, 6), (742, 7), (826, 8)]
# Formas que solo sirven de adorno o de combate: nunca se eligen como miembro de equipo
_COSMETIC_BASES = {"pikachu"}
_BATTLE_ONLY = ("totem", "gmax", "eternamax", "busted", "meteor", "school", "noice", "zen", "complete", "10", "10%", "cell", "core")
# Generación en la que aparece cada forma (cuando es posterior a la de su especie base)
_FORME_GEN = {"origin": 4, "sky": 4, "therian": 5, "black": 5, "white": 5, "resolute": 5, "pirouette": 5, "blade": 6, "unbound": 6,
              "ash": 7, "crowned": 8, "wash": 4, "heat": 4, "frost": 4, "fan": 4, "mow": 4, "attack": 3, "defense": 3, "speed": 3,
              "primal": 6, "starter": 7, "alola": 7, "galar": 8, "hisui": 9, "paldea": 9, "hero": 9, "stellar": 9, "terastal": 9}


_GL_CACHE: Dict[Any, Any] = {}


def dex_gen(num: int) -> int:
    for last, g in _DEX_LAST:
        if num <= last:
            return g
    return 9


def move_gen_from_num(num: int) -> int:
    for last, g in _MOVE_LAST:
        if num <= last:
            return g
    return 9


@lru_cache(maxsize=1)
def _items_extra() -> Dict[str, Any]:
    return json.loads((DATA / "items_extra.json").read_text(encoding="utf-8"))


def item_gen(item_id: str) -> Optional[int]:
    """Generación en que se introdujo el objeto; None si los datos no lo dicen (se asume disponible)."""
    g = (_items_extra().get(item_id) or {}).get("gen")
    return int(g) if g else None


def forme_ok(entry: Dict[str, Any], gen: int, is_champions: bool = False) -> bool:
    """¿Existe esta forma/especie en la generación? (la numeración de Pokédex ya filtra especies nuevas)"""
    if entry.get("num", 9999) > _DEX_LAST[min(gen, 9) - 1][0]:
        return False
    forme = (entry.get("forme") or "").lower()
    base = re.sub(r"[^a-z0-9]", "", (entry.get("baseSpecies") or entry.get("name") or "").lower())
    if not forme or forme == "base":
        return True
    if base in _COSMETIC_BASES:
        return False
    if any(t in forme.split("-") or forme == t for t in ("totem", "gmax", "eternamax")) or "totem" in forme:
        return False
    if entry.get("is_mega"):
        if is_champions:
            return True
        stone = re.sub(r"[^a-z0-9]", "", str(entry.get("requiredItem") or "").lower())
        sg = item_gen(stone) if stone else None
        return (sg or 6) <= gen  # las Megas de Z-A traen piedras de Gen 9: no existen en Gen 6/7
    for tok in re.split(r"[-\s]", forme):
        if tok in _FORME_GEN and _FORME_GEN[tok] > gen:
            return False
    return True


@lru_cache(maxsize=1)
def _learn_codes() -> Dict[str, Dict[str, int]]:
    """especie -> movimiento -> menor generación en que se aprende (según los códigos de learnsets.json)."""
    raw = json.loads((DATA / "learnsets.json").read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, int]] = {}
    for sp, moves in raw.items():
        d: Dict[str, int] = {}
        for mv, codes in moves.items():
            gens = [int(c[0]) for c in codes if c and c[0].isdigit()]
            if gens:
                d[mv] = min(gens)
        out[sp] = d
    return out


def gen_learnset(entry: Optional[Dict[str, Any]], gen: Optional[int], move_gen: Optional[Dict[str, int]] = None) -> Set[str]:
    """
    Movimientos que la especie puede tener EN esa generación: propios + forma base + preevoluciones, aprendidos
    en esa generación o antes, y que el movimiento ya exista. Gen 1-2: los datos solo traen códigos desde Gen 3,
    así que se aceptan los que existían entonces y la especie aprende en cualquier generación (mejor esfuerzo).
    """
    from src.services import pokedex_service as pds
    pds._load_compendium_files()
    cache, extra = pds._POKEDEX_CACHE, pds._POKE_EXTRA
    codes = _learn_codes()
    ckey = (re.sub(r"[^a-z0-9]", "", str((entry or {}).get("id") or (entry or {}).get("name") or "").lower()), gen, move_gen is None)
    if ckey in _GL_CACHE:
        return set(_GL_CACHE[ckey])
    out: Set[str] = set()
    seen: Set[str] = set()
    stack = [entry]
    nid = lambda x: re.sub(r"[^a-z0-9]", "", str(x).lower())
    while stack:
        e = stack.pop()
        if not e:
            continue
        eid = nid(e.get("id") or e.get("name"))
        if eid in seen:
            continue
        seen.add(eid)
        for mv in e.get("learnset") or []:
            m = nid(mv)
            lg = codes.get(eid, {}).get(m)
            if gen is None or (gen < 3) or lg is None or lg <= gen:
                if move_gen is None or gen is None or move_gen.get(m, 9) <= gen:
                    out.add(m)
        base = e.get("baseSpecies")
        if base and nid(base) != eid:
            stack.append(cache.get(nid(base)))
        prevo = (extra.get(eid) or {}).get("prevo")
        if prevo:
            stack.append(cache.get(nid(prevo)))
    _GL_CACHE[ckey] = frozenset(out)
    return out
