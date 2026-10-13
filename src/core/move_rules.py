"""Reglas de coherencia de movimientos de un set (protecciones y pivotes)."""
from typing import Dict, Iterable, List


def norm_move(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


# Familia de protecciones individuales: un set nunca debe llevar dos a la vez.
PROTECT_FAMILY = {
    "protect", "detect", "kingsshield", "spikyshield", "banefulbunker",
    "obstruct", "silktrap", "burningbulwark", "maxguard",
}

# Movimientos que sacan al usuario del campo tras actuar (pivotes reales).
PIVOT_MOVES = {
    "uturn", "voltswitch", "flipturn", "partingshot", "teleport",
    "batonpass", "shedtail", "chillyreception",
}


def protect_moves(moves: Iterable[str]) -> List[str]:
    return [m for m in moves if norm_move(m) in PROTECT_FAMILY]


def has_pivot(moves: Iterable[str]) -> bool:
    return any(norm_move(m) in PIVOT_MOVES for m in moves)


def pivot_moves(moves: Iterable[str]) -> List[str]:
    return [m for m in moves if norm_move(m) in PIVOT_MOVES]


def drop_extra_protects(moves: List[str]) -> List[str]:
    """Conserva solo la primera protección (la de mayor prioridad en el set) y quita las demás."""
    seen = False
    out: List[str] = []
    for m in moves:
        if norm_move(m) in PROTECT_FAMILY:
            if seen:
                continue
            seen = True
        out.append(m)
    return out
