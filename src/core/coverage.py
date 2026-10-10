"""
Módulo de Coberturas, Descripciones de Efectos y Briefing Táctico Verificado.
Extrae traducciones directamente de las bases de datos locales (moves.json, etc.)
para garantizar sincronía 100% con el Compendio y el Frontend.
"""
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

from src.core.move_rules import has_pivot, pivot_moves
from src.core.optimizer import NATURE_MODIFIERS, STAT_NAMES_ES
from src.core.types import calc_type_multiplier, get_move_effective_type_and_power
from src.services.ability_categories import classify as classify_ability
from src.services.smogon import normalize_id
from src.core.era_rules import get_historical_override, move_category, get_historical_move_type

logger = logging.getLogger("uvicorn")
DATA_DIR = Path("src/data")

# Almacenes de Bases de Datos Locales
LOCAL_DBS: Dict[str, Dict[str, Any]] = {"abilities": {}, "items": {}, "moves": {}}
LOCAL_I18N_CACHE: Dict[str, Dict[str, str]] = {"abilities": {}, "items": {}, "moves": {}}

_AB_CAT_ES = {
    "forme": "cambio", "weather": "clima/terreno", "type": "cambio de tipo", "entry": "al entrar",
    "contact": "castigo", "items": "objetos", "status": "estados", "speed": "velocidad",
    "defense": "defensiva", "healing": "curación", "utility": "utilidad", "offense": "ofensiva",
    "stats": "stats", "passive": "pasiva",
}

def _load_coverage_dbs():
    """Carga los JSON locales que usa el Compendio para extraer las traducciones oficiales."""
    if LOCAL_DBS["moves"]: 
        return
    for db_name in ["abilities", "items", "moves"]:
        path = DATA_DIR / f"{db_name}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    LOCAL_DBS[db_name] = json.load(f)
            except Exception as e:
                logger.error(f"Error cargando {db_name}.json: {e}")

    for i18n_file in ["descriptions_full.json", "i18n_data.json"]:
        path = DATA_DIR / i18n_file
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for cat in ("abilities", "items", "moves"):
                        if cat in data and isinstance(data[cat], dict):
                            for k, v in data[cat].items():
                                desc_val = v.get("desc_es") or v.get("desc") if isinstance(v, dict) else str(v)
                                if desc_val:
                                    LOCAL_I18N_CACHE[cat][normalize_id(k)] = desc_val
            except Exception:
                pass

async def ensure_showdown_descriptions_loaded():
    """
    Función de compatibilidad para las rutas de la API.
    Ahora carga las bases de datos locales en lugar de descargar de Showdown.
    """
    _load_coverage_dbs()

def _extract_local_desc(category: str, term_id: str, lang: str = "es") -> str:
    """Busca recursivamente la descripción en español en los archivos locales."""
    _load_coverage_dbs()
    norm_id = normalize_id(term_id)
    
    # 1. Buscar en el archivo de caché I18N
    if lang == "es" and norm_id in LOCAL_I18N_CACHE[category]:
        return LOCAL_I18N_CACHE[category][norm_id]
        
    # 2. Buscar las llaves _es dentro de moves.json / items.json directamente
    obj = LOCAL_DBS[category].get(norm_id, {})
    if lang == "es":
        for k in ["desc_es", "shortDesc_es", "short_desc_es", "efecto_es"]:
            if obj.get(k): 
                return str(obj[k])
            
    # 3. Fallback al inglés si no hay traducción local
    for k in ["desc", "shortDesc", "short_desc"]:
        if obj.get(k): 
            return str(obj[k])
        
    return ""


def get_nature_description_es(nature: str) -> str:
    if nature in NATURE_MODIFIERS:
        inc, dec = NATURE_MODIFIERS[nature]
        return f"Aumenta {STAT_NAMES_ES.get(inc, inc)} (+10%) y reduce {STAT_NAMES_ES.get(dec, dec)} (-10%)."
    return "Naturaleza neutra (no altera ninguna estadística)."


def get_item_description_es(item_name: str, poke_name: str = "", gen: int = 9, lang: str = "es") -> str:
    it_id = normalize_id(item_name)
    
    # Prioridad: Sobreescrituras históricas (ej. Wiki Berry Gen 7)
    hist = get_historical_override("items", it_id, gen, lang)
    if hist and lang in hist: 
        return hist[lang]
    
    # Gemas elementales (Gen 5)
    if "gem" in it_id and it_id != "normalgem":
        val = "50%" if gen <= 5 else "30%"
        return f"Aumenta un {val} la potencia del primer ataque de su tipo respectivo. Uso único."
        
    desc = _extract_local_desc("items", it_id, lang)
    if not desc and lang == "es":
        if item_name.endswith("ite") or "ite " in item_name or it_id.endswith("ite"):
            return f"Megapiedra equipada que permite a {poke_name or 'su portador'} megaevolucionar en combate."
        if it_id.endswith("iumz") or item_name.endswith("ium Z") or item_name.endswith(" Z"):
            return f"Cristal Z equipado que permite a {poke_name or 'su portador'} ejecutar su Movimiento Z una vez."
            
    return desc or f"Objeto equipado de {poke_name or 'su portador'}."


def get_ability_description_es(ability_name: str, gen: int = 9, lang: str = "es") -> str:
    ab_id = normalize_id(ability_name)
    
    hist = get_historical_override("abilities", ab_id, gen, lang)
    if hist and lang in hist: 
        return hist[lang]
    
    desc = _extract_local_desc("abilities", ab_id, lang)
    return desc or f"Habilidad distintiva de {ability_name}."


def get_move_rich_details(move_name: str, legal_moves: Dict[str, Any], gen: int = 9, lang: str = "es") -> Dict[str, Any]:
    _load_coverage_dbs()
    m_id = normalize_id(move_name)
    local_m = legal_moves.get(m_id) or LOCAL_DBS["moves"].get(m_id, {})
    
    hist = get_historical_override("moves", m_id, gen, lang)
    is_hist = bool(hist)
    
    modern_type = local_m.get("type", "Normal")
    m_type = get_historical_move_type(m_id, modern_type, gen)
    
    bp = hist.get("basePower") if is_hist and "basePower" in hist else local_m.get("basePower", 0)
    
    modern_cat = local_m.get("category", "Status")
    cat = move_category(m_type, modern_cat, bp, gen)
    
    raw_acc = hist.get("accuracy") if is_hist and "accuracy" in hist else local_m.get("accuracy", 100)
    acc_str = "—" if raw_acc is True else f"{raw_acc}%"
    prio = local_m.get("priority", 0)
    
    if is_hist and lang in hist:
        desc = hist[lang]
    else:
        desc = _extract_local_desc("moves", m_id, lang)
        
    if not desc:
        if cat == "Status": 
            desc = f"Movimiento táctico de categoría Estado y tipo {m_type}."
        else: 
            desc = f"Ataque {'físico' if cat == 'Physical' else 'especial'} de tipo {m_type} con {bp} de potencia."

    return {
        "name": move_name, 
        "type": m_type, 
        "category": cat, 
        "basePower": bp, 
        "accuracy": acc_str, 
        "priority": prio, 
        "desc": desc, 
        "is_historical": is_hist or modern_type != m_type or modern_cat != cat
    }


def build_verified_tactical_briefing(
    final_team: List[Dict[str, Any]], threat_entries: List[Dict[str, Any]], pool: Dict[str, Any], era=None,
) -> Tuple[str, str, str, List[str]]:
    legal_moves = pool["legal_moves"]
    is_doubles = pool["format"]["game_type"] == "doubles"
    gen_num = era.get("gen", 9) if era else 9

    no_abilities = bool(era) and not era.get("has_abilities", True)
    ability_facts = ["(Esta generación NO tiene habilidades.)"] if no_abilities else []
    for p in final_team:
        if no_abilities: continue
        ab = p["ability"]
        desc = get_ability_description_es(ab, gen_num)
        cat_id, _ = classify_ability(desc, "", re.sub(r"[^a-z0-9]", "", str(ab).lower()))
        ability_facts.append(f"- {p['species']} con '{ab}' [{_AB_CAT_ES.get(cat_id, cat_id)}] + {p['item']}: {desc}")

    lead_1 = final_team[0] if len(final_team) > 0 else {"species": "Lead 1", "moves": ["Protect"]}
    lead_2 = final_team[1] if len(final_team) > 1 else lead_1
    for cand in final_team[1:]:
        if any(m in cand.get("moves", []) for m in ["Fake Out", "Tailwind", "Rage Powder", "Follow Me"]):
            lead_2 = cand
            break

    bench_pivot = next((p for p in final_team if p not in [lead_1, lead_2]), (final_team[2] if len(final_team) > 2 else lead_1))

    l1_setup = next((m for m in lead_1["moves"] if m in ["Tailwind", "Nasty Plot", "Swords Dance", "Dragon Dance"]), lead_1["moves"][0])
    l1_attack = next((m for m in lead_1["moves"] if m not in ["Protect", "Tailwind", "Nasty Plot", "Swords Dance"]), lead_1["moves"][0])
    l2_support = next((m for m in lead_2["moves"] if m in ["Fake Out", "Tailwind", "Rage Powder", "Follow Me", "Parting Shot", "U-turn"]), lead_2["moves"][0])
    l2_followup = next((m for m in lead_2["moves"] if m != l2_support and m != "Protect"), lead_2["moves"][0])

    switch_phrase = f"pivota con {pivot_moves(lead_2['moves'])[0]} hacia {bench_pivot['species']}" if has_pivot(lead_2.get("moves", [])) else f"cambia a {bench_pivot['species']}"
    lead_plan_str = f"Dobles. Abre con {lead_1['species']} y {lead_2['species']}. {lead_2['species']} usa {l2_support} permitiendo a {lead_1['species']} usar {l1_setup}." if is_doubles else f"Abre con {lead_2['species']} usando {l2_support} para dar entrada a {lead_1['species']}."

    calculated_threats = []
    for threat in threat_entries[:2]:
        t_name = threat["name"]
        t_types = threat.get("types", ["Normal"])
        best_score, best_counter_poke, best_move_name, best_mult = -1.0, final_team[0], final_team[0]["moves"][0], 1.0

        for our_p in final_team:
            for mv in our_p.get("moves", []):
                eff_type, bp, _ = get_move_effective_type_and_power(mv, our_p, legal_moves)
                if bp <= 0: continue
                mult = calc_type_multiplier(eff_type, t_types)
                if mult == 0.0: continue
                score = bp * mult * (1.5 if eff_type in our_p["types"] else 1.0)
                if score > best_score:
                    best_score, best_counter_poke, best_move_name, best_mult = score, our_p, mv, mult

        eff_label = "daño supereficaz" if best_mult >= 2.0 else "fuerte daño neutro"
        calculated_threats.append(f"{t_name}: lo neutralizamos con {best_counter_poke['species']} usando {best_move_name} ({eff_label}).")

    p0 = final_team[0]['species'] if len(final_team) > 0 else 'Slot 1'
    p3 = final_team[3]['species'] if len(final_team) > 3 else 'Slot 4'
    core_summary_fallback = f"Equipo balanceado que aprovecha a {p0} y {p3} para presionar."
    
    with_pivot = [f"{p['species']}" for p in final_team if has_pivot(p.get("moves", []))]
    without_pivot = [p["species"] for p in final_team if not has_pivot(p.get("moves", []))]
    pivot_block = f"PIVOTES:\n- Con pivote: {', '.join(with_pivot) or 'ninguno'}\n- Sin pivote (Cambio Manual): {', '.join(without_pivot) or 'ninguno'}"

    briefing_text = "\n".join(ability_facts) + f"\n\nPLAN DE APERTURA:\n{lead_plan_str}\n\n{pivot_block}\n\nCOUNTERS:\n" + "\n".join([f"- {ct}" for ct in calculated_threats])
    return briefing_text, core_summary_fallback, lead_plan_str, calculated_threats