"""
Módulo de cálculo de Estadísticas a Nivel 50, Modificadores de Naturaleza y Roles Tácticos.
Asigna etiquetas reales de rol según inversión de EVs, ataques y utilidad.
"""
from typing import Any, Dict, List, Tuple

NATURE_MODIFIERS: Dict[str, Tuple[str, str]] = {
    "Adamant": ("atk", "sp_atk"),
    "Brave": ("atk", "speed"),
    "Lonely": ("atk", "defense"),
    "Naughty": ("atk", "sp_def"),
    "Bold": ("defense", "atk"),
    "Impish": ("defense", "sp_atk"),
    "Lax": ("defense", "sp_def"),
    "Relaxed": ("defense", "speed"),
    "Modest": ("sp_atk", "atk"),
    "Mild": ("sp_atk", "defense"),
    "Quiet": ("sp_atk", "speed"),
    "Rash": ("sp_atk", "sp_def"),
    "Calm": ("sp_def", "atk"),
    "Careful": ("sp_def", "sp_atk"),
    "Gentle": ("sp_def", "defense"),
    "Sassy": ("sp_def", "speed"),
    "Timid": ("speed", "atk"),
    "Hasty": ("speed", "defense"),
    "Jolly": ("speed", "sp_atk"),
    "Naive": ("speed", "sp_def"),
}

STAT_NAMES_ES = {
    "hp": "PS",
    "atk": "Ataque Físico",
    "defense": "Defensa Física",
    "sp_atk": "Ataque Especial",
    "sp_def": "Defensa Especial",
    "speed": "Velocidad",
}


def normalize_base_stats(raw_bs: Dict[str, int]) -> Dict[str, int]:
    return {
        "hp": raw_bs.get("hp", 80),
        "atk": raw_bs.get("atk", 80),
        "defense": raw_bs.get("def", raw_bs.get("defense", 80)),
        "sp_atk": raw_bs.get("spa", raw_bs.get("sp_atk", 80)),
        "sp_def": raw_bs.get("spd", raw_bs.get("sp_def", 80)),
        "speed": raw_bs.get("spe", raw_bs.get("speed", 80)),
    }


def normalize_evs_dict(evs: Dict[str, int], is_physical: bool, fast: bool) -> Dict[str, int]:
    total = sum(evs.values())
    if 10 <= total <= 70 and max(evs.values()) <= 32:
        converted = {}
        for k, v in evs.items():
            if v >= 30:
                converted[k] = 252
            elif v <= 0:
                converted[k] = 0
            elif v <= 2:
                converted[k] = 4
            else:
                converted[k] = min(252, v * 8)
        return converted

    if total == 0 or total > 510:
        return {
            "hp": 4 if fast else 252,
            "atk": 252 if is_physical else 0,
            "defense": 0,
            "sp_atk": 0 if is_physical else 252,
            "sp_def": 4,
            "speed": 252 if fast else 0,
        }
    return evs


def calculate_level_50_stats(norm_base_stats: Dict[str, int], evs: Dict[str, int], nature: str) -> Dict[str, int]:
    ivs = 31
    stats: Dict[str, int] = {}

    hp_base = norm_base_stats.get("hp", 80)
    hp_ev = evs.get("hp", 0)
    if hp_base == 1:
        stats["hp"] = 1
    else:
        stats["hp"] = int(((2 * hp_base + ivs + (hp_ev // 4)) * 50) // 100) + 60

    inc_stat, dec_stat = NATURE_MODIFIERS.get(nature, ("", ""))

    for stat_key in ["atk", "defense", "sp_atk", "sp_def", "speed"]:
        base = norm_base_stats.get(stat_key, 80)
        ev = evs.get(stat_key, 0)
        val = int(((2 * base + ivs + (ev // 4)) * 50) // 100) + 5
        if stat_key == inc_stat:
            val = int(val * 1.1)
        elif stat_key == dec_stat:
            val = int(val * 0.9)
        stats[stat_key] = val

    return stats


def compute_accurate_role_label(
    poke_entry: Dict[str, Any],
    ability: str,
    moves: List[str],
    evs: Dict[str, int],
    weather_abilities: Dict[str, str],
) -> str:
    atk_ev = evs.get("atk", 0)
    spa_ev = evs.get("sp_atk", 0)
    is_phys_spread = atk_ev >= spa_ev

    has_tailwind = "Tailwind" in moves
    has_tr = "Trick Room" in moves
    has_fakeout = "Fake Out" in moves
    has_redirection = "Rage Powder" in moves or "Follow Me" in moves
    has_screens = "Reflect" in moves or "Light Screen" in moves
    has_twave_or_spore = any(m in moves for m in ["Thunder Wave", "Spore", "Will-O-Wisp", "Toxic", "Yawn"])

    if poke_entry.get("is_mega"):
        if has_tailwind:
            return f"Mega Sweeper {'Físico' if is_phys_spread else 'Especial'} & Tailwind"
        return f"Mega Sweeper {'Físico' if is_phys_spread else 'Especial'}"

    # Setters de Clima y Terreno
    if ability in weather_abilities:
        return f"Setter de Clima ({weather_abilities[ability]}) & Soporte"
    if ability == "Grassy Surge":
        return "Control de Terreno (Grassy Surge) & Pivote"
    if ability == "Psychic Surge":
        return "Control de Terreno (Psychic Surge) & Soporte"

    # Soportes y utilidades de prioridad
    if ability == "Prankster":
        return "Soporte de Control (Prankster)"
    if has_screens:
        return "Soporte de Pantallas & Control"
    if has_redirection:
        return "Redirección & Soporte Defensivo"
    if ability == "Intimidate" and has_fakeout:
        return "Pivote Defensivo (Intimidate + Fake Out)"
    if ability in ["Armor Tail", "Queenly Majesty"]:
        return "Bloqueo de Prioridad & Soporte"
    if has_tr:
        return "Setter de Trick Room & Soporte"
    if has_tailwind:
        return f"Control de Velocidad (Tailwind) & {'Atacante Físico' if is_phys_spread else 'Atacante Especial'}"

    # Detección estricta de soporte defensivo si no tiene inversión ofensiva
    if max(atk_ev, spa_ev) < 80:
        if has_twave_or_spore or has_fakeout:
            return "Soporte & Control de Estado"
        return "Tanque Defensivo & Utilidad"

    # Atacantes con inversión real
    spe_ev = evs.get("speed", 0)
    if spe_ev >= 180:
        return f"Fast Sweeper {'Físico' if is_phys_spread else 'Especial'}"
    return f"Wallbreaker {'Físico' if is_phys_spread else 'Especial'}"