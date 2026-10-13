"""
Módulo de cálculo de Tipos Elementales, Debilidades, Resistencias e Inmunidades.
"""
from typing import Any, Dict, List, Tuple
from src.services.smogon import normalize_id

TYPE_CHART: Dict[str, Dict[str, float]] = {
    "Normal": {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water": {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
    "Grass": {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
    "Ground": {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying": {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
    "Bug": {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Dark": {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Fairy": {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5},
}


def calc_type_multiplier(move_type: str, target_types: List[str]) -> float:
    mult = 1.0
    chart_row = TYPE_CHART.get(move_type, {})
    for t in target_types:
        mult *= chart_row.get(t, 1.0)
    return mult


def compute_defensive_matchups(poke_types: List[str], ability: str = "") -> Dict[str, List[str]]:
    all_types = list(TYPE_CHART.keys())
    matchups: Dict[str, List[str]] = {
        "x4": [],
        "x2": [],
        "x1": [],
        "x05": [],
        "x025": [],
        "x0": [],
    }

    ability_immunities = {
        "Levitate": "Ground",
        "Earth Eater": "Ground",
        "Flash Fire": "Fire",
        "Well-Baked Body": "Fire",
        "Water Absorb": "Water",
        "Storm Drain": "Water",
        "Dry Skin": "Water",
        "Volt Absorb": "Electric",
        "Lightning Rod": "Electric",
        "Motor Drive": "Electric",
        "Sap Sipper": "Grass",
    }
    immune_by_ability = ability_immunities.get(ability)

    for atk_type in all_types:
        if immune_by_ability == atk_type:
            mult = 0.0
        else:
            mult = 1.0
            for def_t in poke_types:
                mult *= TYPE_CHART.get(atk_type, {}).get(def_t, 1.0)

        if mult >= 4.0:
            matchups["x4"].append(atk_type)
        elif mult == 2.0:
            matchups["x2"].append(atk_type)
        elif mult == 1.0:
            matchups["x1"].append(atk_type)
        elif mult == 0.5:
            matchups["x05"].append(atk_type)
        elif mult == 0.25:
            matchups["x025"].append(atk_type)
        elif mult == 0.0:
            matchups["x0"].append(atk_type)

    return matchups


def get_move_effective_type_and_power(move_name: str, poke: Dict[str, Any], legal_moves: Dict[str, Any]) -> Tuple[str, int, str]:
    m_id = normalize_id(move_name)
    m_info = legal_moves.get(m_id, {})
    m_type = m_info.get("type", "Normal")
    bp = m_info.get("basePower", 0)
    cat = m_info.get("category", "Status")

    if cat == "Status" or bp <= 0:
        return m_type, 0, cat

    ab = poke.get("ability", "")
    if m_type == "Normal":
        if ab == "Aerilate":
            m_type = "Flying"
            bp = int(bp * 1.2)
        elif ab == "Pixilate":
            m_type = "Fairy"
            bp = int(bp * 1.2)

    return m_type, bp, cat