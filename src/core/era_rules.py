"""
Reglas históricas por generación para el Analizador y Constructor: tabla de tipos,
habilidades legales con retcones históricos, categoría de movimientos y mecánicas de era.
"""
import re
from typing import Any, Dict, List, Optional, Set

ABILITY_IMMUNITIES = {
    "levitate": ("Ground", 3), "flashfire": ("Fire", 3), "waterabsorb": ("Water", 3),
    "voltabsorb": ("Electric", 3), "lightningrod": ("Electric", 5), "stormdrain": ("Water", 5),
    "motordrive": ("Electric", 4), "sapsipper": ("Grass", 5), "dryskin": ("Water", 4),
    "eartheater": ("Ground", 9), "wellbakedbody": ("Fire", 9), "windrider": ("Flying", 9),
}

HISTORICAL_ABILITY_RETCONS = {
    "gengar": {(3, 6): ["Levitate"], (7, 9): ["Cursed Body"]},
    "haunter": {(3, 9): ["Levitate"]},
    "gastly": {(3, 9): ["Levitate"]},
    "koffing": {(3, 7): ["Levitate"], (8, 9): ["Levitate", "Neutralizing Gas", "Stench"]},
    "weezing": {(3, 7): ["Levitate"], (8, 9): ["Levitate", "Neutralizing Gas", "Stench"]},
    "weezinggalar": {(8, 9): ["Levitate", "Neutralizing Gas", "Misty Surge"]},
    "pelipper": {(3, 6): ["Keen Eye"], (7, 9): ["Keen Eye", "Drizzle", "Rain Dish"]},
    "torkoal": {(3, 4): ["White Smoke"], (5, 6): ["White Smoke", "Shell Armor"], (7, 9): ["White Smoke", "Drought", "Shell Armor"]},
    "gigalith": {(5, 6): ["Sturdy", "Sand Force"], (7, 9): ["Sturdy", "Sand Stream", "Sand Force"]},
    "vanilluxe": {(5, 6): ["Ice Body", "Weak Armor"], (7, 9): ["Ice Body", "Snow Warning", "Weak Armor"]},
    "raikou": {(3, 4): ["Pressure"], (5, 6): ["Pressure", "Volt Absorb"], (7, 9): ["Pressure", "Inner Focus"]},
    "entei": {(3, 4): ["Pressure"], (5, 6): ["Pressure", "Flash Fire"], (7, 9): ["Pressure", "Inner Focus"]},
    "suicune": {(3, 4): ["Pressure"], (5, 6): ["Pressure", "Water Absorb"], (7, 9): ["Pressure", "Inner Focus"]},
    "zapdos": {(3, 4): ["Pressure"], (5, 5): ["Pressure", "Lightning Rod"], (6, 9): ["Pressure", "Static"]},
    "chandelure": {(5, 5): ["Flash Fire", "Flame Body"], (6, 9): ["Flash Fire", "Flame Body", "Infiltrator"]},
    "bronzong": {(4, 4): ["Levitate", "Heatproof"], (5, 9): ["Levitate", "Heatproof", "Heavy Metal"]},
}

# MATRIZ HISTÓRICA DE TEXTOS (Gen-Aware + i18n-Aware)
HISTORICAL_OVERRIDES = {
    "items": {
        "wikiberry": {(3, 6): {"es": "Restaura un 12.5% de los PS máximos al bajar del 50%.", "en": "Restores 12.5% max HP at 50% HP or less."}, (7, 7): {"es": "Restaura un 50% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 50% max HP at 25% HP or less (may confuse)."}, (8, 9): {"es": "Restaura un 33.3% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 33.3% max HP at 25% HP or less (may confuse)."}},
        "aguavberry": {(3, 6): {"es": "Restaura un 12.5% de los PS máximos al bajar del 50%.", "en": "Restores 12.5% max HP at 50% HP or less."}, (7, 7): {"es": "Restaura un 50% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 50% max HP at 25% HP or less (may confuse)."}, (8, 9): {"es": "Restaura un 33.3% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 33.3% max HP at 25% HP or less (may confuse)."}},
        "magoberry": {(3, 6): {"es": "Restaura un 12.5% de los PS máximos al bajar del 50%.", "en": "Restores 12.5% max HP at 50% HP or less."}, (7, 7): {"es": "Restaura un 50% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 50% max HP at 25% HP or less (may confuse)."}, (8, 9): {"es": "Restaura un 33.3% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 33.3% max HP at 25% HP or less (may confuse)."}},
        "figyberry": {(3, 6): {"es": "Restaura un 12.5% de los PS máximos al bajar del 50%.", "en": "Restores 12.5% max HP at 50% HP or less."}, (7, 7): {"es": "Restaura un 50% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 50% max HP at 25% HP or less (may confuse)."}, (8, 9): {"es": "Restaura un 33.3% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 33.3% max HP at 25% HP or less (may confuse)."}},
        "iapapaberry": {(3, 6): {"es": "Restaura un 12.5% de los PS máximos al bajar del 50%.", "en": "Restores 12.5% max HP at 50% HP or less."}, (7, 7): {"es": "Restaura un 50% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 50% max HP at 25% HP or less (may confuse)."}, (8, 9): {"es": "Restaura un 33.3% de los PS máximos al bajar del 25% (puede confundir).", "en": "Restores 33.3% max HP at 25% HP or less (may confuse)."}},
        "souldew": {(3, 6): {"es": "Aumenta un 50% el Ataque Especial y la Defensa Especial de Latios y Latias.", "en": "Boosts Sp. Atk and Sp. Def of Latios and Latias by 50%."}, (7, 9): {"es": "Aumenta un 20% la potencia de los ataques Dragón y Psíquico del portador.", "en": "Boosts Dragon and Psychic moves by 20%."}},
    },
    "abilities": {
        "galewings": {(6, 6): {"es": "Otorga prioridad +1 a todos los movimientos de tipo Volador.", "en": "Gives priority +1 to Flying-type moves."}, (7, 9): {"es": "Otorga prioridad +1 a movimientos Volador solo si el usuario tiene el 100% de PS.", "en": "Gives priority +1 to Flying-type moves only at full HP."}},
        "prankster": {(5, 6): {"es": "Otorga prioridad +1 a los movimientos de categoría Estado.", "en": "Gives priority +1 to Status moves."}, (7, 9): {"es": "Otorga prioridad +1 a movimientos de Estado (los tipo Siniestro son inmunes).", "en": "Gives priority +1 to Status moves. Dark types are immune."}},
        "disguise": {(7, 7): {"es": "Absorbe el primer ataque recibido sin que el Pokémon sufra daño.", "en": "Takes 0 damage from the first attack received."}, (8, 9): {"es": "Absorbe el primer ataque, pero pierde 1/8 de sus PS máximos al romperse.", "en": "Takes 1/8 max HP damage when disguise is busted."}},
        "electricsurge": {(7, 7): {"es": "Activa Campo Eléctrico por 5 turnos: potencia ataques Eléctricos un 50% e impide dormir.", "en": "Sets Electric Terrain for 5 turns (Boosts Electric by 50%, prevents sleep)."}, (8, 9): {"es": "Activa Campo Eléctrico por 5 turnos: potencia ataques Eléctricos un 30% e impide dormir.", "en": "Sets Electric Terrain for 5 turns (Boosts Electric by 30%, prevents sleep)."}},
        "grassysurge": {(7, 7): {"es": "Activa Campo de Hierba por 5 turnos: potencia ataques Planta un 50% y cura 1/16 PS/turno.", "en": "Sets Grassy Terrain for 5 turns (Boosts Grass by 50%, heals 1/16 HP)."}, (8, 9): {"es": "Activa Campo de Hierba por 5 turnos: potencia ataques Planta un 30% y cura 1/16 PS/turno.", "en": "Sets Grassy Terrain for 5 turns (Boosts Grass by 30%, heals 1/16 HP)."}},
        "psychicsurge": {(7, 7): {"es": "Activa Campo Psíquico por 5 turnos: potencia ataques Psíquicos un 50% y bloquea prioridad.", "en": "Sets Psychic Terrain for 5 turns (Boosts Psychic by 50%, blocks priority)."}, (8, 9): {"es": "Activa Campo Psíquico por 5 turnos: potencia ataques Psíquicos un 30% y bloquea prioridad.", "en": "Sets Psychic Terrain for 5 turns (Boosts Psychic by 30%, blocks priority)."}},
    },
    "moves": {
        "knockoff": {(3, 5): {"basePower": 20, "es": "Golpea y quita el objeto al objetivo.", "en": "Removes the target's held item."}, (6, 9): {"basePower": 65, "es": "Potencia +50% si el rival lleva objeto, y se lo quita por el resto del combate.", "en": "1.5x damage if target holds an item. Removes item."}},
        "rapidspin": {(2, 7): {"basePower": 20, "es": "Libera al usuario de hazards (Púas, Trampa Rocas) y ataduras.", "en": "Frees user from hazards/binds."}, (8, 9): {"basePower": 50, "es": "Libera al usuario de hazards/ataduras y aumenta su Velocidad en +1 nivel.", "en": "Frees user from hazards/binds, raises Speed by 1."}},
        "thunderwave": {(1, 6): {"accuracy": 100, "es": "Onda que paraliza al objetivo, reduciendo su velocidad a un 25%.", "en": "Paralyzes target, reducing Speed to 25%."}, (7, 9): {"accuracy": 90, "es": "Onda que paraliza al objetivo, reduciendo su velocidad a un 50%.", "en": "Paralyzes target, reducing Speed to 50%."}},
        "hiddenpower": {(2, 5): {"basePower": "Varies", "es": "Su tipo y potencia (hasta 70 BP) varían según los IVs.", "en": "Type and power (up to 70) vary based on IVs."}, (6, 7): {"basePower": 60, "es": "Su tipo varía según los IVs. Potencia fija de 60 BP.", "en": "Type varies based on IVs. Power is 60 BP."}, (8, 9): {"basePower": 60, "es": "(Movimiento eliminado del juego).", "en": "(Move removed from the game)."}},
    }
}

PHYSICAL_TYPES_OLD = {"Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel"}


def norm(name: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def get_historical_override(category: str, term_id: str, gen: int, lang: str = "es") -> Optional[Dict[str, Any]]:
    norm_id = norm(term_id)
    overrides = HISTORICAL_OVERRIDES.get(category, {}).get(norm_id)
    if not overrides:
        return None
    for (g_min, g_max), data in overrides.items():
        if g_min <= gen <= g_max:
            return data
    return None


def get_historical_move_type(m_id: str, modern_type: str, gen: int) -> str:
    """Devuelve el tipo histórico de un movimiento retroactivamente modificado."""
    m_id = norm(m_id)
    
    if gen < 6 and modern_type == "Fairy":
        return "Normal"
        
    if gen == 1:
        if m_id == "bite": return "Normal"
        if m_id == "gust": return "Normal"
        if m_id == "karatechop": return "Normal"
        if m_id == "sandattack": return "Normal"
        
    return modern_type


def type_chart_for_gen(modern: Dict[str, Dict[str, float]], gen: int) -> Dict[str, Dict[str, float]]:
    chart = {atk: dict(row) for atk, row in modern.items()}
    if gen < 6:
        chart.pop("Fairy", None)
        for row in chart.values():
            row.pop("Fairy", None)
        if "Ghost" in chart and "Steel" in chart["Ghost"]:
            chart["Ghost"]["Steel"] = 0.5
        if "Dark" in chart and "Steel" in chart["Dark"]:
            chart["Dark"]["Steel"] = 0.5
    if gen < 2:
        for t in ("Dark", "Steel"):
            chart.pop(t, None)
            for row in chart.values():
                row.pop(t, None)
    return chart


def era_types(types: List[str], gen: int) -> List[str]:
    out = [t for t in types if not (gen < 6 and t == "Fairy") and not (gen < 2 and t in ("Dark", "Steel"))]
    return out or ["Normal"]


def effectiveness(chart: Dict[str, Dict[str, float]], atk_type: str, def_types: List[str],
                  ability: str = "", gen: int = 9) -> float:
    mult = 1.0
    for d in def_types:
        mult *= chart.get(atk_type, {}).get(d, 1.0)
    imm = ABILITY_IMMUNITIES.get(norm(ability))
    if imm and imm[0] == atk_type and gen >= imm[1]:
        return 0.0
    return mult


def find_entry(cache: Dict[str, Any], species: str) -> Optional[Dict[str, Any]]:
    clean = norm(species)
    if clean in cache:
        return cache[clean]
    for p in cache.values():
        if norm(p.get("name")) == clean:
            return p
    return None


def legal_abilities(entry: Optional[Dict[str, Any]], gen: int) -> List[str]:
    if not entry or gen < 3:
        return []
    sp_id = norm(entry.get("baseSpecies") or entry.get("name") or "")
    if sp_id in HISTORICAL_ABILITY_RETCONS:
        for (g_min, g_max), abils in HISTORICAL_ABILITY_RETCONS[sp_id].items():
            if g_min <= gen <= g_max:
                return list(abils)
    amap = entry.get("abilities_map") or {str(i): a for i, a in enumerate(entry.get("abilities", []))}
    out: List[str] = []
    for slot, ab in amap.items():
        if slot in ("0", "1") or (slot in ("H", "S") and gen >= 5):
            if ab and ab not in out:
                out.append(ab)
    return out


def move_category(move_type: str, declared: str, base_power: Any, gen: int) -> str:
    try:
        bp = int(base_power or 0)
    except (TypeError, ValueError):
        bp = 0
    if declared == "Status" or bp <= 0:
        return "Status"
    if gen <= 3:
        return "Physical" if move_type in PHYSICAL_TYPES_OLD else "Special"
    return declared


def pick_threat_candidates(
    legal_pokes: Dict[str, Dict[str, Any]], exclude_ids: Set[str], chart: Dict[str, Dict[str, float]],
    weak_counts: Dict[str, int], gen: int, allow_megas: bool, total: int = 4,
) -> List[Dict[str, Any]]:
    regional = ("alola", "galar", "hisui", "paldea")
    targets = [t for t, n in sorted(weak_counts.items(), key=lambda kv: -kv[1]) if n >= 1 and t in chart][:3]

    def score(p: Dict[str, Any]) -> float:
        bs = p.get("baseStats", {})
        return max(bs.get("atk", 0), bs.get("spa", 0)) + 0.35 * bs.get("spe", 0) + 0.1 * p.get("bst", 0)

    ranked = []
    for pid, p in legal_pokes.items():
        forme = (p.get("forme") or "Base")
        if pid in exclude_ids or p.get("tier") in ("NFE", "LC") or p.get("bst", 0) < 450:
            continue
        if forme != "Base" and not (p.get("is_mega") and allow_megas) and not any(r in forme.lower() for r in regional):
            continue
        ranked.append((score(p), pid, p, era_types(p.get("types", ["Normal"]), gen)))
    ranked.sort(key=lambda r: -r[0])

    picked: List[Dict[str, Any]] = []
    used: Set[str] = set()

    def add_candidate(cand_tuple):
        _, pid, p, types = cand_tuple
        used.add(pid)
        picked.append({
            "name": p.get("name", pid), "types": types, "bst": p.get("bst", 0),
            "abilities": legal_abilities(p, gen) or p.get("abilities", [])[:2],
            "base_species": p.get("baseSpecies", p.get("name", pid)),
        })

    for t in targets:
        n = 0
        for item in ranked:
            if item[1] not in used and t in item[3]:
                add_candidate(item)
                n += 1
                if n >= 2: break
    for item in ranked:
        if len(picked) >= total: break
        if item[1] not in used:
            add_candidate(item)
    return picked[:max(total, 2)]


def era_mechanics(gen: int) -> Dict[str, Any]:
    return {
        "gen": gen, "has_abilities": gen >= 3, "has_items": gen >= 2, "has_natures": gen >= 3,
        "modern_evs": gen >= 3, "stat_level": 100 if gen <= 2 else 50,
        "allow_megas": gen in (6, 7), "allow_z_moves": gen == 7, "allow_dynamax": gen == 8, "allow_tera": gen == 9,
    }


def calc_stats_gen12(base: Dict[str, int], gen: int, level: int = 100) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for k in ("hp", "atk", "defense", "sp_atk", "sp_def", "speed"):
        b = base.get(k, 0)
        if gen == 1 and k == "sp_def":
            b = base.get("sp_atk", b)
        core = ((b + 15) * 2 + 63) * level // 100
        out[k] = core + level + 10 if k == "hp" else core + 5
    return out


def defensive_matchups_for_gen(types: List[str], ability: str, chart: Dict[str, Dict[str, float]], gen: int) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {"x4": [], "x2": [], "x1": [], "x05": [], "x025": [], "x0": []}
    for atk in chart:
        m = effectiveness(chart, atk, types, ability or "", gen)
        key = "x4" if m >= 4 else "x2" if m >= 2 else "x0" if m == 0 else "x025" if m <= 0.25 else "x05" if m < 1 else "x1"
        out[key].append(atk)
    return out


def describe_era(gen: int, max_dex: int, species_names: Optional[List[str]] = None) -> str:
    lines = [f"RESTRICCIÓN DE ERA (OBLIGATORIA): formato Generación {gen}. Pokédex válido: SOLO #001–#{max_dex:03d}."]
    if gen == 1: lines.append("Mecánicas: sin habilidades, sin objetos, sin naturalezas y sin EVs modernos.")
    elif gen == 2: lines.append("Mecánicas: con objetos, pero sin habilidades ni naturalezas.")
    if species_names: lines.append("ESPECIES LEGALES: " + ", ".join(species_names))
    return "\n".join(lines)


def guide_era_rules(era: Dict[str, Any]) -> str:
    missing = []
    if not era.get("has_abilities", True): missing.append("habilidades")
    if not era.get("has_items", True): missing.append("objetos")
    if not era.get("has_natures", True): missing.append("naturalezas")
    if not era.get("modern_evs", True): missing.append("EVs/repartos de esfuerzo")
    if not missing: return ""
    return f"ERA GENERACIÓN {era.get('gen')}: NO existen {', '.join(missing)}. No los menciones."