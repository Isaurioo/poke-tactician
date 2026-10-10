"""
Planificador de EVs por benchmarks (Nivel 50, IV 31).

Sustituye al reparto rígido 252/252/4 que se aplicaba a todos los Pokémon cuando no había
estadísticas de uso reales. Aquí cada set recibe un spread según su ROL:

  * Velocidad: se invierte lo justo para superar un benchmark del meta ("speed creep"):
    el Pokémon más rápido que puede superar con su velocidad máxima, sin gastar EVs de más.
    Bajo Tailwind / clima de velocidad (x2) se necesita muy poco; en Trick Room, cero.
  * Ofensiva: 252 solo para sweepers / wallbreakers / atacantes de Trick Room. El soporte
    y los tanques no la maximizan.
  * Bulk: lo que sobra se reparte entre PS / Def / DefE maximizando el MÍNIMO entre la
    resistencia física (PS x Def) y la especial (PS x DefE).

Matemática del juego a nivel 50: stat = floor((2*B + 31 + floor(EV/4)) / 2) + 5 (PS: + 60).
Los primeros 4 EVs dan +1 punto de stat y cada +8 EVs dan otro, por eso los valores
eficientes son 0, 4, 12, 20, ... 252 (= 4 + 8k) y el total efectivo máximo es 508.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.optimizer import NATURE_MODIFIERS

STAT_KEYS = ("hp", "atk", "defense", "sp_atk", "sp_def", "speed")
MAX_POINTS = 32            # 32 puntos = 252 EVs
MAX_TOTAL_EVS = 508        # 510 es el tope legal; con pasos 4+8k el máximo aprovechable es 508

# Habilidades que duplican la Velocidad bajo su clima / campo
WEATHER_SPEED_ABILITIES = {
    "Swift Swim": "Rain", "Chlorophyll": "Sun", "Sand Rush": "Sand", "Slush Rush": "Snow",
}

# Movimientos que definen a un Pokémon de soporte / pivote
STRONG_SUPPORT_MOVES = {
    "fakeout", "helpinghand", "followme", "ragepowder", "wideguard", "quickguard", "partingshot",
    "reflect", "lightscreen", "auroraveil", "encore", "taunt", "willowisp", "spore", "sleeppowder",
    "thunderwave", "coaching", "lifedew", "healpulse", "afteryou", "allyswitch", "haze", "yawn",
    "tailwind", "trickroom", "screech", "faketears", "painsplit", "wish", "memento", "strengthsap",
}
# Movimientos utilitarios que también llevan muchos atacantes (no los convierten en soporte)
SOFT_UTILITY_MOVES = {"icywind", "electroweb", "snarl", "pollenpuff", "toxic", "charm", "tickle", "decorate"}
SUPPORT_MOVES = STRONG_SUPPORT_MOVES | SOFT_UTILITY_MOVES
SETUP_MOVES = {
    "swordsdance", "dragondance", "nastyplot", "quiverdance", "calmmind", "bulkup", "bellydrum",
    "shellsmash", "tailglow", "rockpolish", "coil", "geomancy", "victorydance", "shiftgear",
    "curse", "agility", "workup",
}


# --------------------------------------------------------------------------- #
# Matemática de stats
# --------------------------------------------------------------------------- #
def ev_for_points(points: int) -> int:
    """EVs que cuesta tener `points` puntos de stat: 0, 4, 12, 20, ..., 252."""
    return 0 if points <= 0 else 8 * points - 4


def calc_stat(stat: str, base: int, ev: int, nature: str) -> int:
    """Stat final a nivel 50 con IV 31 (idéntico a optimizer.calculate_level_50_stats)."""
    if stat == "hp":
        return 1 if base == 1 else ((2 * base + 31 + ev // 4) * 50) // 100 + 60
    val = ((2 * base + 31 + ev // 4) * 50) // 100 + 5
    inc, dec = NATURE_MODIFIERS.get(nature, ("", ""))
    if stat == inc:
        return int(val * 1.1)
    if stat == dec:
        return int(val * 0.9)
    return val


def _speed(base: int, points: int, nature: str, scarf: bool) -> int:
    s = calc_stat("speed", base, ev_for_points(points), nature)
    return int(s * 1.5) if scarf else s


def tier_speed(tier_base: int) -> int:
    """Velocidad de un Pokémon neutro con 252 EVs y la base indicada (el 'benchmark')."""
    return calc_stat("speed", tier_base, 252, "Hardy")


def points_to_outspeed(base: int, nature: str, target: int, scarf: bool = False, multiplier: int = 1) -> Optional[int]:
    """Puntos mínimos para que (velocidad * multiplicador) sea >= target. None si es imposible."""
    for p in range(0, MAX_POINTS + 1):
        if _speed(base, p, nature, scarf) * multiplier >= target:
            return p
    return None


def pick_speed_tier(base_speed: int, nature: str, scarf: bool) -> Tuple[Optional[int], int]:
    """
    Mayor benchmark (base múltiplo de 5) que se puede SUPERAR con la velocidad máxima y los
    puntos mínimos necesarios para lograrlo. Devuelve (base_benchmark, puntos).
    """
    for tier in range(150, 25, -5):
        pts = points_to_outspeed(base_speed, nature, tier_speed(tier) + 1, scarf)
        if pts is not None:
            return tier, pts
    return None, 0


# --------------------------------------------------------------------------- #
# Rol y ofensiva
# --------------------------------------------------------------------------- #
def _norm(name: Any) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _bp(m: Dict[str, Any]) -> int:
    try:
        return int(m.get("basePower") or 0)
    except (TypeError, ValueError):
        return 0


def offense_profile(moves_info: List[Dict[str, Any]], base: Dict[str, int]) -> Tuple[str, int]:
    """('Physical' | 'Special', nº de movimientos de daño)."""
    phys = sum(_bp(m) for m in moves_info if m.get("category") == "Physical")
    spec = sum(_bp(m) for m in moves_info if m.get("category") == "Special")
    n_attacks = sum(
        1 for m in moves_info if _bp(m) >= 50 and _norm(m.get("name", "")) not in SUPPORT_MOVES
    )
    if phys == 0 and spec == 0:
        return ("Physical" if base["atk"] >= base["sp_atk"] else "Special"), n_attacks
    return ("Physical" if phys >= spec else "Special"), n_attacks


def classify_role(
    base: Dict[str, int], move_ids: Set[str], off_cat: str, n_attacks: int, team_tr: bool,
) -> str:
    off_base = base["atk"] if off_cat == "Physical" else base["sp_atk"]
    bulk = base["hp"] + base["defense"] + base["sp_def"]
    strong = len(move_ids & STRONG_SUPPORT_MOVES)
    strong_no_tr = len((move_ids - {"trickroom"}) & STRONG_SUPPORT_MOVES)
    setup = bool(move_ids & SETUP_MOVES)
    slow = base["speed"] <= 85

    # Atacante de Trick Room (también el que lo pone si pega fuerte)
    if (team_tr or "trickroom" in move_ids) and slow and off_base >= 85 and strong_no_tr < 2:
        return "tr_attacker"
    if "trickroom" in move_ids and off_base < 100:
        return "support"
    # Soporte / pivote
    if strong >= 2 and off_base < 125:
        return "support"
    if strong >= 1 and (off_base < 100 or n_attacks <= 1):
        return "support"
    # Tanque: muy resistente y sin ofensiva dominante
    if bulk >= 300 and off_base < 110 and not setup:
        return "tank"
    if off_base >= 95 or setup or (off_base >= 80 and bulk < 270):
        return "sweeper" if base["speed"] >= 90 else "wallbreaker"
    if bulk >= 270:
        return "tank"
    return "balanced"


# --------------------------------------------------------------------------- #
# Naturaleza
# --------------------------------------------------------------------------- #
def _nature_for(inc: str, dec: str, fallback: str) -> str:
    for name, pair in NATURE_MODIFIERS.items():
        if pair == (inc, dec):
            return name
    return fallback


def choose_nature(
    role: str, off_cat: str, base: Dict[str, int], scarf: bool, speed_tier_mode: bool, team_tr: bool,
) -> str:
    atk_stat = "atk" if off_cat == "Physical" else "sp_atk"
    other_off = "sp_atk" if off_cat == "Physical" else "atk"

    if role == "tr_attacker":
        return _nature_for(atk_stat, "speed", "Brave" if off_cat == "Physical" else "Quiet")

    if role in ("sweeper", "wallbreaker", "balanced"):
        if role == "sweeper" and speed_tier_mode and base["speed"] >= 95 and not scarf:
            return _nature_for("speed", other_off, "Jolly" if off_cat == "Physical" else "Timid")
        return _nature_for(atk_stat, other_off, "Adamant" if off_cat == "Physical" else "Modest")

    # support / tank: +defensa más débil, -ataque que no se usa (o -Velocidad en Trick Room)
    weaker = "defense" if base["defense"] <= base["sp_def"] else "sp_def"
    if team_tr and base["speed"] <= 85:
        minus = "speed"
    elif off_cat == "Physical" and base["sp_atk"] <= base["atk"] + 20:
        minus = "sp_atk"
    elif off_cat == "Special" and base["atk"] <= base["sp_atk"] + 20:
        minus = "atk"
    else:
        minus = other_off
    return _nature_for(weaker, minus, "Bold" if weaker == "defense" else "Calm")


# --------------------------------------------------------------------------- #
# Reparto del bulk
# --------------------------------------------------------------------------- #
def allocate_bulk(base: Dict[str, int], nature: str, budget: int, hp_first_points: int = 0) -> Dict[str, int]:
    """
    Reparte `budget` EVs entre PS / Def / DefE punto a punto, eligiendo siempre el que más
    sube el mínimo entre resistencia física (PS*Def) y especial (PS*DefE).
    `hp_first_points` reserva primero esa cantidad de puntos de PS (32 = 252 EVs), porque PS
    mejora ambas resistencias; el resto se reparte equilibrando físico y especial.
    """
    pts = {"hp": 0, "defense": 0, "sp_def": 0}
    spent = 0

    if hp_first_points > 0 and base["hp"] != 1:
        while pts["hp"] < min(MAX_POINTS, hp_first_points):
            extra = ev_for_points(pts["hp"] + 1) - ev_for_points(pts["hp"])
            if spent + extra > budget:
                break
            spent += extra
            pts["hp"] += 1

    def score(p: Dict[str, int]) -> Tuple[int, int]:
        hp = calc_stat("hp", base["hp"], ev_for_points(p["hp"]), nature)
        df = calc_stat("defense", base["defense"], ev_for_points(p["defense"]), nature)
        sd = calc_stat("sp_def", base["sp_def"], ev_for_points(p["sp_def"]), nature)
        return min(hp * df, hp * sd), hp * df + hp * sd

    while True:
        best_key, best_score = None, None
        for key in ("hp", "defense", "sp_def"):
            if pts[key] >= MAX_POINTS or (key == "hp" and base["hp"] == 1):
                continue
            extra = ev_for_points(pts[key] + 1) - ev_for_points(pts[key])
            if spent + extra > budget:
                continue
            trial = dict(pts)
            trial[key] += 1
            sc = score(trial)
            if best_score is None or sc > best_score:      # empate -> gana el primero (PS)
                best_key, best_score = key, sc
        if best_key is None:
            break
        spent += ev_for_points(pts[best_key] + 1) - ev_for_points(pts[best_key])
        pts[best_key] += 1

    return {k: ev_for_points(v) for k, v in pts.items()}


# --------------------------------------------------------------------------- #
# API principal
# --------------------------------------------------------------------------- #
def plan_spread(
    base_stats: Dict[str, int],
    moves_info: List[Dict[str, Any]],
    item: str,
    ability: str,
    team_tailwind: bool,
    team_tr: bool,
    team_weathers: Set[str],
) -> Tuple[Dict[str, int], str, Dict[str, Any]]:
    """Devuelve (evs, naturaleza, plan) para un set. `plan` describe las decisiones tomadas."""
    base = {k: int(base_stats.get(k, 80)) for k in STAT_KEYS}
    move_ids = {_norm(m.get("name", "")) for m in moves_info}
    scarf = _norm(item) == "choicescarf"
    off_cat, n_attacks = offense_profile(moves_info, base)
    role = classify_role(base, move_ids, off_cat, n_attacks, team_tr)

    weather_needed = WEATHER_SPEED_ABILITIES.get(ability)
    weather_ally = bool(weather_needed and weather_needed in team_weathers)
    tailwind_ally = team_tailwind and "tailwind" not in move_ids
    spd = base["speed"]

    # --- modo de velocidad ---
    if role == "tr_attacker":
        mode = "none"
    elif weather_ally and spd <= 110:
        mode = "weather"
    elif role == "support":
        mode = "tier" if (("tailwind" in move_ids or move_ids & {"icywind", "electroweb", "thunderwave"}) and spd >= 90) else "none"
    elif role == "sweeper":
        mode = "tailwind" if (tailwind_ally and spd < 95 and not scarf) else "tier"
    elif role == "wallbreaker":
        mode = "tailwind" if tailwind_ally else ("tier" if spd >= 75 else "none")
    elif role == "balanced":
        mode = "tailwind" if (tailwind_ally and spd >= 55) else ("tier" if spd >= 90 else "none")
    else:  # tank
        mode = "tailwind" if (tailwind_ally and spd >= 55) else "none"

    nature = choose_nature(role, off_cat, base, scarf, mode == "tier", team_tr)

    # --- velocidad ---
    speed_pts, beats = 0, None
    if mode == "tier":
        beats, speed_pts = pick_speed_tier(spd, nature, scarf)
        if beats is None:
            mode = "none"
    elif mode in ("tailwind", "weather"):
        # x2 de Tailwind/clima: basta con superar, duplicada, a un Pokémon neutro máx. de base 120
        target = tier_speed(120) + 1
        pts = points_to_outspeed(spd, nature, target, scarf, multiplier=2)
        speed_pts = pts if pts is not None else MAX_POINTS
        beats = 120

    # --- ofensiva ---
    atk_stat = "atk" if off_cat == "Physical" else "sp_atk"
    if role in ("sweeper", "wallbreaker", "tr_attacker"):
        off_pts = MAX_POINTS
    elif role == "balanced":
        off_pts = 16
    elif n_attacks >= 2 and (base[atk_stat] >= 100):
        off_pts = 1
    else:
        off_pts = 0

    evs = {k: 0 for k in STAT_KEYS}
    evs["speed"] = ev_for_points(speed_pts)
    evs[atk_stat] = ev_for_points(off_pts)

    budget = MAX_TOTAL_EVS - evs["speed"] - evs[atk_stat]
    # Sweepers (rápidos): el sobrante es poco y va a PS. Atacantes lentos: reciben golpes antes de
    # mover, así que reparten el sobrante entre PS y su defensa más débil. Resto: PS primero.
    hp_first = 16 if role in ("wallbreaker", "tr_attacker") else MAX_POINTS
    evs.update(allocate_bulk(base, nature, budget, hp_first_points=hp_first))

    plan = {
        "source": "benchmark",
        "role": role,
        "offense": off_cat if off_pts >= 16 else None,
        "speed": {"mode": mode, "beats_base": beats, "scarf": scarf and mode == "tier"},
    }
    return evs, nature, plan
