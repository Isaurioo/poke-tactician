"""
Motor Constructor Adaptativo de Equipos Competitivos (Teambuilder).
Garantiza compatibilidad generacional estricta, habilidades legales por era,
cláusulas de formato (exactamente 1 Mega, 1 Cristal Z en Gen 7, Restringidos en Ubers),
unicidad de ítems (máx. 2 Leftovers en Smogon), exclusión de climas antagónicos y bloqueo de recargas.
"""
import difflib
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.coverage import (
    get_ability_description_es,
    get_item_description_es,
    get_move_rich_details,
    get_nature_description_es,
)
from src.core.optimizer import (
    calculate_level_50_stats,
    compute_accurate_role_label,
    normalize_base_stats,
    normalize_evs_dict,
)
from src.core.ev_planner import plan_spread
from src.core.team_validator import full_learnset
from src.core.move_rules import PROTECT_FAMILY, drop_extra_protects, protect_moves
from src.core.entity_extraction import norm_text, resolve_requests, resolve_species_name
from src.core.era_rules import (
    calc_stats_gen12,
    defensive_matchups_for_gen,
    era_types,
    legal_abilities,
    type_chart_for_gen,
)
from src.core.types import TYPE_CHART, compute_defensive_matchups
from src.services.smogon import normalize_id, parse_spread_string

logger = logging.getLogger("uvicorn")

WEATHER_ABILITIES = {
    "Drizzle": "Rain",
    "Drought": "Sun",
    "Orichalcum Pulse": "Sun",
    "Sand Stream": "Sand",
    "Snow Warning": "Snow",
}

WEATHER_DEPENDENT_ABILITIES = {
    "Sand Rush": "Sand",
    "Sand Veil": "Sand",
    "Swift Swim": "Rain",
    "Chlorophyll": "Sun",
    "Solar Power": "Sun",
    "Slush Rush": "Snow",
}

TERRAIN_ABILITIES = {
    "Grassy Surge": "Grassy",
    "Psychic Surge": "Psychic",
    "Electric Surge": "Electric",
    "Hadron Engine": "Electric",
    "Misty Surge": "Misty",
}

TERRAIN_DEPENDENT_ITEMS = {
    "Grassy Seed": "Grassy",
    "Psychic Seed": "Psychic",
    "Electric Seed": "Electric",
    "Misty Seed": "Misty",
}

Z_CRYSTALS_BY_TYPE = {
    "Normal": "Normalium Z", "Fire": "Firium Z", "Water": "Waterium Z",
    "Electric": "Electrium Z", "Grass": "Grassium Z", "Ice": "Icium Z",
    "Fighting": "Fightinium Z", "Poison": "Poisonium Z", "Ground": "Groundium Z",
    "Flying": "Flyinium Z", "Psychic": "Psychium Z", "Bug": "Buginium Z",
    "Rock": "Rockium Z", "Ghost": "Ghostium Z", "Dragon": "Dragonium Z",
    "Dark": "Darkinium Z", "Steel": "Steelium Z", "Fairy": "Fairium Z",
}

SOUND_MOVES = {
    "hypervoice", "snarl", "torchsong", "alluringvoice", "bugbuzz",
    "clangingscales", "overdrive", "partingshot", "perishsong", "psychicnoise",
}

PHYSICAL_SETUP_MOVES = {"swordsdance", "dragondance", "bulkup", "coil", "bellydrum", "curse", "howl"}
SPECIAL_SETUP_MOVES = {"nastyplot", "calmmind", "quiverdance", "tailglow"}
TWO_TURN_CHARGE_MOVES = {"electroshot", "solarbeam", "solarblade", "meteorbeam", "geomancy", "skullbash", "skyattack"}

BANNED_RECHARGE_MOVES = {
    "blastburn", "frenzyplant", "hydrocannon", "gigaimpact", "hyperbeam",
    "roaroftime", "rockwrecker", "eternabeam"
}

MANDATORY_FORM_ITEMS = {
    "zacian": "Rusted Sword",
    "zaciancrowned": "Rusted Sword",
    "zamazenta": "Rusted Shield",
    "zamazentacrowned": "Rusted Shield",
    "giratinaorigin": "Griseous Orb",
    "dialgaorigin": "Adamant Crystal",
    "palkiaorigin": "Lustrous Globe",
    "ogerponwellspring": "Wellspring Mask",
    "ogerponhearthflame": "Hearthflame Mask",
    "ogerponcornerstone": "Cornerstone Mask",
}

TR_SETTERS = {
    "farigiraf", "indeedeef", "hatterene", "sinistcha", "porygon2",
    "dusclops", "bronzong", "mimikyu", "armarouge", "cresselia",
    "chandelure", "reuniclus", "oranguru", "slowbro", "slowking", "slowkinggalar"
}
TR_ABUSERS = {
    "ursaluna", "ursalunabloodmoon", "torkoal", "kingambit", "amoonguss",
    "ironhands", "conkeldurr", "gastrodon", "camerupt", "drampa", "glastrier",
    "vikavolt", "scizor", "abomasnow", "ampharos"
}
TR_MEGAS = {
    "cameruptmega", "abomasnowmega", "ampharosmega", "sableyemega",
    "mawilemega", "steelixmega", "audinomega", "blastoisemega", "slowbromega"
}

RAIN_SETTERS = {"pelipper", "politoed", "kyogre"}
RAIN_ABUSERS = {"archaludon", "basculegion", "basculegionf", "barraskewda", "kingdra", "palafin", "urshifurapidstrike", "ludicolo"}
SUN_SETTERS = {"torkoal", "ninetales", "koraidon", "groudon"}
SUN_ABUSERS = {"fluttermane", "ragingbolt", "walkingwake", "gougingfire", "roaringmoon", "venusaur", "charizard"}
SAND_SETTERS = {"tyranitar", "hippowdon"}
SAND_ABUSERS = {"excadrill", "houndstone", "garchomp", "lycanroc"}

KNOWN_SPECIAL_ATTACKERS = {
    "torkoal", "gholdengo", "hatterene", "farigiraf", "sinistcha", "armarouge",
    "pelipper", "chandelure", "hydreigon", "volcarona", "gengar", "primarina",
    "indeedeef", "indeedee", "charizard", "blastoise"
}


def _legacy_parse_tactical_intent(prompt: str) -> Dict[str, Any]:
    p = prompt.lower()
    wants_2_megas = bool(re.search(r"\b(2|dos|dual)\s+megas?\b", p))
    wants_mega = "mega" in p or wants_2_megas

    wants_tr = any(k in p for k in ["espacio raro", "trick room", "trickroom", "tr", "raro"])
    wants_tailwind = any(k in p for k in ["tailwind", "viento afin", "viento afín"])

    wants_rain = any(k in p for k in ["lluvia", "rain", "drizzle"])
    wants_sun = any(k in p for k in ["sol", "sun", "drought", "soleado"]) and not wants_tr
    wants_sand = any(k in p for k in ["arena", "sand", "sandstorm", "tormenta de arena"])
    wants_snow = any(k in p for k in ["nieve", "snow", "granizo", "hail"])

    wants_grassy = any(k in p for k in ["hierba", "grassy", "terreno de hierba"])
    wants_psychic = any(k in p for k in ["psiquico", "psíquico", "psychic terrain"])
    wants_electric = any(k in p for k in ["electrico", "eléctrico", "electric terrain"])

    return {
        "wants_mega": wants_mega,
        "wants_2_megas": wants_2_megas,
        "wants_tr": wants_tr,
        "wants_tailwind": wants_tailwind,
        "wants_rain": wants_rain,
        "wants_sun": wants_sun,
        "wants_sand": wants_sand,
        "wants_snow": wants_snow,
        "wants_grassy": wants_grassy,
        "wants_psychic": wants_psychic,
        "wants_electric": wants_electric,
    }


def parse_tactical_intent(prompt: str) -> Dict[str, Any]:
    out = _legacy_parse_tactical_intent(prompt)
    p = norm_text(prompt)

    def has(pat: str) -> bool:
        return bool(re.search(pat, p))

    wants_tr = has(r"\btrick\s*room\b|\bespacio\s+raro\b|\bdistorsion\b|\btr\b")
    fixes = {
        "wants_tr": wants_tr,
        "wants_2_megas": has(r"\b(2|dos|deux|two|dual|both|ambas)\s+(megas?|megaevolu\w+)\b"),
        "wants_no_mega": has(r"\b(sin|no|without|sans|pas de)\s+(megas?|megaevol\w*)\b"),
        "wants_mega": has(r"\bmegas?\b|megaevol|\bmega-") and not has(r"\b(sin|no|without|sans|pas de)\s+(megas?|megaevol\w*)\b"),
        "wants_tailwind": has(r"\btailwind\b|\bviento\s+afin\b|\bvent\s+arriere\b"),
        "wants_rain": has(r"\b(lluvia|rain|drizzle|pluie|pluvieux|rain\s*dance)\b"),
        "wants_sun": has(r"\b(sol|sun|sunny|drought|soleado|soleil|ensoleille)\b") and not wants_tr,
        "wants_sand": has(r"\b(arena|sand|sandstorm|sable)\b|tormenta de arena|tempete de sable"),
        "wants_snow": has(r"\b(nieve|snow|granizo|hail|hailstorm|neige|grele)\b"),
        "wants_grassy": has(r"terreno de hierba|grassy (terrain|surge)|champ herbu"),
        "wants_psychic": has(r"terreno psiquico|psychic (terrain|surge)|champ psychique"),
        "wants_electric": has(r"terreno electrico|electric (terrain|surge)|champ electrique"),
    }
    for k, v in fixes.items():
        out[k] = v
    out["wants_perish_trap"] = has(r"\bperish\s*(trap|song)\b|\bcanto\s+mortal\b|\btrampa\s+mortal\b|\brequiem\b|\bpiege\s+mortel\b")
    return out


def build_showdown_sprite_url(poke_entry: Dict[str, Any]) -> str:
    base = normalize_id(poke_entry.get("baseSpecies", ""))
    forme = normalize_id(poke_entry.get("forme", ""))
    new_za_megas = {
        "golisopod", "zeraora", "chandelure", "delphox", "chesnaught", "greninja",
        "dragonite", "hawlucha", "meganium", "feraligatr", "emboar", "excadrill",
        "scolipede", "scrafty", "eelektross", "starmie", "clefable", "victreebel",
        "skarmory", "froslass", "malarmar", "malamar", "drampa", "falinks", "pyroar",
        "floette", "barbaracle", "dragalge", "zygarde",
    }
    if not forme or forme == "base":
        return f"https://play.pokemonshowdown.com/sprites/gen5/{base}.png"
    if poke_entry.get("is_mega") and base in new_za_megas:
        return f"https://play.pokemonshowdown.com/sprites/gen5/{base}.png"
    return f"https://play.pokemonshowdown.com/sprites/gen5/{base}-{forme}.png"


def detect_user_requested_pokemon(
    user_prompt: str,
    legal_pokemon: Dict[str, Dict[str, Any]],
    allow_megas: bool,
) -> List[Dict[str, Any]]:
    cache = _dex_cache()
    entries, _illegal = resolve_requests(user_prompt, cache, legal_pokemon)
    return entries


def build_versatile_context_for_ai(
    pool: Dict[str, Any],
    live_chaos: Dict[str, Any],
    user_prompt: str,
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    mech = pool["mechanics"]
    legal_pokemon: Dict[str, Dict[str, Any]] = pool["legal_pokemon"]
    intent = parse_tactical_intent(user_prompt)

    requested_pokes = detect_user_requested_pokemon(user_prompt, legal_pokemon, mech["allow_megas"])
    seen_bases = {p["baseSpecies"] for p in requested_pokes}

    candidates: List[Tuple[float, Dict[str, Any]]] = []

    for k, p_obj in legal_pokemon.items():
        b_name = normalize_id(p_obj["baseSpecies"])
        p_name = normalize_id(p_obj["name"])
        bs = p_obj.get("baseStats", {})
        spe = bs.get("spe", 80)
        bst = p_obj.get("bst", 450)
        is_mega = p_obj.get("is_mega", False)

        if b_name in seen_bases:
            continue

        score = float(bst) / 10.0

        if intent["wants_tr"]:
            if b_name in TR_SETTERS:
                score += 3000.0
            elif b_name in TR_ABUSERS or spe <= 60:
                score += 2500.0
            if is_mega and (p_name in TR_MEGAS or spe <= 65):
                score += 2800.0
            elif spe >= 105 and b_name not in TR_SETTERS and b_name not in ["incineroar", "amoonguss"]:
                score -= 3000.0

        if intent["wants_rain"]:
            if b_name in RAIN_SETTERS:
                score += 3500.0
            elif b_name in RAIN_ABUSERS:
                score += 2000.0

        if intent["wants_sun"]:
            if b_name in SUN_SETTERS:
                score += 3500.0
            elif b_name in SUN_ABUSERS:
                score += 2000.0

        if intent["wants_sand"]:
            if b_name in SAND_SETTERS:
                score += 3500.0
            elif b_name in SAND_ABUSERS:
                score += 2000.0

        if (intent["wants_mega"] or mech.get("force_mega")) and is_mega:
            score += 2200.0

        if mech.get("force_restricted") and p_obj.get("is_restricted"):
            score += 4000.0

        candidates.append((score, p_obj))
        seen_bases.add(b_name)

    for req_p in requested_pokes:
        for k in [normalize_id(req_p["name"]), normalize_id(req_p["baseSpecies"])]:
            mates = live_chaos.get(k, {}).get("teammates", {})
            for mate_name, weight in sorted(mates.items(), key=lambda x: x[1], reverse=True):
                m_key = normalize_id(mate_name)
                if m_key in legal_pokemon:
                    p_obj = legal_pokemon[m_key]
                    if p_obj["baseSpecies"] not in seen_bases:
                        candidates.append((float(weight) + 500.0, p_obj))
                        seen_bases.add(p_obj["baseSpecies"])

    for poke_key, s_data in sorted(live_chaos.items(), key=lambda x: x[1].get("usage", 0), reverse=True):
        if poke_key in legal_pokemon:
            p_obj = legal_pokemon[poke_key]
            if p_obj["baseSpecies"] not in seen_bases:
                candidates.append((float(s_data.get("usage", 0)) * 100.0 + 300.0, p_obj))
                seen_bases.add(p_obj["baseSpecies"])

    candidates.sort(key=lambda x: x[0], reverse=True)
    meta_pool = [c[1] for c in candidates[:60]]

    if len(meta_pool) < 6:
        for p_obj in legal_pokemon.values():
            if p_obj["baseSpecies"] not in {m["baseSpecies"] for m in meta_pool}:
                meta_pool.append(p_obj)
            if len(meta_pool) >= 12:
                break

    catalog_lines = []
    for p in requested_pokes + meta_pool:
        bs = p.get("baseStats", {})
        offense_type = "Físico" if bs.get("atk", 80) >= bs.get("spa", 80) else "Especial"
        speed_tier = f"Spe {bs.get('spe', 80)}"
        catalog_lines.append(
            f"- {p['name']} ({'/'.join(p['types'])}) | Habilidades: {', '.join(p.get('abilities', []))} | {offense_type} ({speed_tier})"
        )

    req_str = (
        "POKÉMON / CONDICIÓN OBLIGATORIA DEL USUARIO:\n"
        + (f"* Solicitud del jugador: {user_prompt}\n" if not requested_pokes else "")
        + "\n".join([f"* {p['name']} ({'/'.join(p['types'])})" for p in requested_pokes])
    )

    context_str = f"{req_str}\n\nCATÁLOGO META RECOMENDADO:\n" + "\n".join(catalog_lines)
    return context_str, requested_pokes, meta_pool


def dedupe_protect_moves(chosen_moves: List[str], learnset: Any, legal_moves: Dict[str, Any], poke_entry: Dict[str, Any]) -> List[str]:
    moves = drop_extra_protects(list(chosen_moves))
    if len(moves) >= 4 or len(moves) == len(chosen_moves):
        return moves
    have = {normalize_id(m) for m in moves}
    used_types = {(legal_moves.get(normalize_id(m)) or {}).get("type") for m in moves}
    types = poke_entry.get("types", [])
    ranked = []
    for m_id in learnset or []:
        info = legal_moves.get(m_id)
        if not info or m_id in have or m_id in PROTECT_FAMILY or m_id in BANNED_RECHARGE_MOVES:
            continue
        bp = info.get("basePower") or 0
        if info.get("category") == "Status" or bp < 60:
            continue
        score = bp + (30 if info.get("type") in types else 0) - (40 if info.get("type") in used_types else 0)
        ranked.append((score, info.get("name", m_id)))
    ranked.sort(reverse=True)
    for _, name in ranked:
        if len(moves) >= 4:
            break
        moves.append(name)
    return moves


def sanitize_team_protects(final_team: List[Dict[str, Any]]) -> None:
    for card in final_team:
        moves = card.get("moves") or []
        if len(protect_moves(moves)) > 1:
            kept = drop_extra_protects(moves)
            card["moves"] = kept
            details = card.get("details")
            if isinstance(details, dict) and details.get("moves_info"):
                details["moves_info"] = [mi for mi in details["moves_info"] if mi.get("name") in kept]


def _dex_cache() -> Dict[str, Any]:
    from src.services import pokedex_service
    pokedex_service._load_compendium_files()
    return pokedex_service._POKEDEX_CACHE


def extract_live_set_for_pokemon(
    poke_entry: Dict[str, Any],
    pool: Dict[str, Any],
    live_chaos: Dict[str, Any],
    smogon_sets: Dict[str, Any],
    used_items: Set[str],
    team_weathers: Set[str],
    team_terrains: Set[str],
    wants_trick_room: bool,
    current_tr_setters_count: int = 0,
    has_fire_sweepers: bool = False,
    has_water_sweepers: bool = False,
    wants_perish_trap: bool = False,
    assign_z_crystal: bool = False,
    leftovers_count: int = 0,
) -> Tuple[Dict[str, Any], int]:
    legal_items = pool["legal_items"]
    legal_moves = pool["legal_moves"]
    mech = pool["mechanics"]
    gen_num = int(mech.get("gen", 9) or 9)
    is_doubles = pool["format"]["game_type"] == "doubles"
    has_grassy_surge = "Grassy" in team_terrains

    p_key = normalize_id(poke_entry["name"])
    base_key = normalize_id(poke_entry["baseSpecies"])
    
    # HERENCIA DE ATAQUES: Si es una forma regional o alternativa, hereda los ataques de su forma base.
    learnset = full_learnset(poke_entry)  # propios + forma base + preevoluciones
        
    raw_bs = poke_entry.get("baseStats", {})
    norm_bs = normalize_base_stats(raw_bs)
    poke_types = list(poke_entry.get("types", []))

    chaos_data = live_chaos.get(p_key) or live_chaos.get(base_key) or {}

    if base_key in KNOWN_SPECIAL_ATTACKERS:
        default_phys = False
    elif base_key in ["zacian", "zaciancrowned", "zamazenta", "zamazentacrowned", "urshifu", "urshifurapidstrike", "kingambit", "conkeldurr"]:
        default_phys = True
    else:
        live_moves_list = list(chaos_data.get("moves", {}).keys())[:8]
        phys_votes = 0
        spec_votes = 0
        for mv_k in live_moves_list:
            m_norm = normalize_id(mv_k)
            if m_norm in legal_moves:
                cat = legal_moves[m_norm].get("category")
                if cat == "Physical":
                    phys_votes += 1
                elif cat == "Special":
                    spec_votes += 1
        if spec_votes > phys_votes:
            default_phys = False
        elif phys_votes > spec_votes:
            default_phys = True
        else:
            default_phys = norm_bs["atk"] > norm_bs["sp_atk"]

    is_fast = norm_bs["speed"] >= 95 and not wants_trick_room

    # 1. Habilidad legal por era histórica (Gengar con Levitate en Gen 3-6, etc.)
    historic_abs = legal_abilities(poke_entry, gen_num)
    official_abilities = historic_abs if historic_abs else poke_entry.get("abilities", ["Pressure"])
    ability_lookup = {normalize_id(a): a for a in official_abilities}
    chosen_ability = official_abilities[0]
    live_ab_found = False

    if len(official_abilities) > 1:
        for live_ab_key, _ in sorted(chaos_data.get("abilities", {}).items(), key=lambda x: x[1], reverse=True):
            norm_ab = normalize_id(live_ab_key)
            if norm_ab in ability_lookup:
                cand_ab = ability_lookup[norm_ab]
                req_weather = WEATHER_DEPENDENT_ABILITIES.get(cand_ab)
                if req_weather and req_weather not in team_weathers:
                    continue
                chosen_ability = cand_ab
                live_ab_found = True
                break
        if not live_ab_found:
            # Sin datos de uso: preferir la habilidad que define el rol (clima, terreno, Intimidate...)
            key_ab = next((a for a in official_abilities if a in WEATHER_ABILITIES or a in TERRAIN_ABILITIES
                           or a in {"Intimidate", "Prankster", "Regenerator"}), None)
            chosen_ability = key_ab or chosen_ability

    # 2. Naturaleza y EVs
    ev_source = "default"
    is_tr_user = wants_trick_room and (base_key in TR_SETTERS or base_key in TR_ABUSERS or norm_bs["speed"] <= 85)
    if is_tr_user:
        nature = "Brave" if default_phys else "Quiet"
        evs = {
            "hp": 252,
            "atk": 252 if default_phys else 0,
            "defense": 4 if default_phys else 0,
            "sp_atk": 0 if default_phys else 252,
            "sp_def": 0 if default_phys else 4,
            "speed": 0,
        }
    else:
        nature = ("Jolly" if is_fast else "Adamant") if default_phys else ("Timid" if is_fast else "Modest")
        evs = normalize_evs_dict({}, default_phys, is_fast)

        live_spreads = chaos_data.get("spreads", {})
        if live_spreads:
            top_spread_str = sorted(live_spreads.items(), key=lambda x: x[1], reverse=True)[0][0]
            parsed_nat, parsed_evs = parse_spread_string(top_spread_str)
            if wants_trick_room and parsed_nat in ["Jolly", "Timid", "Hasty", "Naive"]:
                parsed_nat = "Brave" if default_phys else "Quiet"
                parsed_evs["speed"] = 0
            nature = parsed_nat
            evs = normalize_evs_dict(parsed_evs, default_phys, is_fast)
            ev_source = "usage"

    is_physical_set = evs.get("atk", 0) >= evs.get("sp_atk", 0) if (evs.get("atk", 0) != evs.get("sp_atk", 0)) else default_phys
    target_category = "Physical" if is_physical_set else "Special"
    power_herb_available = "powerherb" in legal_items and "Power Herb" not in used_items

    # 3. Ítem Mandatorio de Forma o Megapiedra
    final_item = None
    if base_key in MANDATORY_FORM_ITEMS or p_key in MANDATORY_FORM_ITEMS:
        mandatory_it_name = MANDATORY_FORM_ITEMS.get(p_key) or MANDATORY_FORM_ITEMS.get(base_key)
        it_clean = normalize_id(mandatory_it_name)
        if it_clean in legal_items or gen_num >= 8:
            final_item = mandatory_it_name
    elif poke_entry.get("requiredItem"):
        final_item = poke_entry["requiredItem"]
    elif poke_entry.get("is_mega"):
        for it_id, it_obj in legal_items.items():
            if it_obj.get("megaStone") and normalize_id(it_obj["megaStone"]) in [base_key, p_key]:
                final_item = it_obj["name"]
                break

    # 4. Movimientos
    chosen_moves: List[str] = []
    attacking_types_used: Set[str] = set()
    live_moves = chaos_data.get("moves", {})

    if base_key in ["zacian", "zaciancrowned"] and final_item == "Rusted Sword":
        chosen_moves.append("Behemoth Blade")
        attacking_types_used.add("Steel")
    elif base_key in ["zamazenta", "zamazentacrowned"] and final_item == "Rusted Shield":
        chosen_moves.append("Behemoth Bash")
        attacking_types_used.add("Steel")

    if wants_trick_room and base_key in TR_SETTERS and current_tr_setters_count < 2:
        if "trickroom" in legal_moves and (not learnset or "trickroom" in learnset):
            if "Trick Room" not in chosen_moves:
                chosen_moves.append(legal_moves["trickroom"]["name"])

    if chosen_ability in ["Aerilate", "Pixilate", "Refrigerate"]:
        primary_ate = "doubleedge" if is_physical_set else "hypervoice"
        if primary_ate in legal_moves and (not learnset or primary_ate in learnset):
            chosen_moves.append(legal_moves[primary_ate]["name"])
            attacking_types_used.add("Flying" if chosen_ability == "Aerilate" else ("Fairy" if chosen_ability == "Pixilate" else "Ice"))

    best_stab_move = None
    best_stab_score = -1.0

    for m_cand, weight in live_moves.items():
        m_cand_id = normalize_id(m_cand)
        if m_cand_id in BANNED_RECHARGE_MOVES:
            continue
        if m_cand_id not in legal_moves or (learnset and m_cand_id not in learnset):
            continue
        m_info = legal_moves[m_cand_id]
        if m_info.get("category") == target_category and m_info.get("type") in poke_types:
            bp = m_info.get("basePower", 0)
            if bp >= 50:
                score = bp * (float(weight) + 1.0)
                if score > best_stab_score:
                    best_stab_score = score
                    best_stab_move = m_info["name"]

    if not best_stab_move and learnset:
        for m_cand_id in learnset:
            if m_cand_id in BANNED_RECHARGE_MOVES or m_cand_id not in legal_moves:
                continue
            m_info = legal_moves[m_cand_id]
            if m_info.get("category") == target_category and m_info.get("type") in poke_types:
                bp = m_info.get("basePower", 0)
                if bp >= 60 and bp > best_stab_score:
                    best_stab_score = bp
                    best_stab_move = m_info["name"]

    if best_stab_move and best_stab_move not in chosen_moves:
        chosen_moves.append(best_stab_move)
        m_obj = legal_moves[normalize_id(best_stab_move)]
        attacking_types_used.add(m_obj.get("type", ""))

    has_psychic_terrain = chosen_ability == "Psychic Surge" or "Psychic" in team_terrains
    for core_util in ["fakeout", "partingshot", "spore", "ragepowder", "followme"]:
        if len(chosen_moves) >= 4:
            break
        if core_util == "fakeout" and has_psychic_terrain:
            continue
        if core_util in live_moves and core_util in legal_moves and (not learnset or core_util in learnset):
            if live_moves[core_util] > 0.12 or base_key in ["incineroar", "amoonguss", "sinistcha", "indeedeef"]:
                m_name = legal_moves[core_util]["name"]
                if m_name not in chosen_moves:
                    chosen_moves.append(m_name)

    for m_raw, _ in sorted(live_moves.items(), key=lambda x: x[1], reverse=True):
        if len(chosen_moves) >= 4:
            break
        m_id = normalize_id(m_raw)
        if m_id == "nothing" or m_id in BANNED_RECHARGE_MOVES or m_id not in legal_moves or (learnset and m_id not in learnset):
            continue

        if m_id == "raindance" and has_fire_sweepers:
            continue
        if m_id == "sunnyday" and has_water_sweepers:
            continue
        if m_id == "fakeout" and (has_psychic_terrain or "Shell Smash" in chosen_moves):
            continue
        if m_id == "trickroom" and (not wants_trick_room or current_tr_setters_count >= 2):
            continue
        if m_id == "tailwind" and wants_trick_room:
            continue
        if not is_physical_set and m_id in PHYSICAL_SETUP_MOVES:
            continue
        if is_physical_set and m_id in SPECIAL_SETUP_MOVES:
            continue
        if m_id == "bodypress" and "Belly Drum" in chosen_moves:
            continue
        if m_id == "bellydrum" and "Body Press" in chosen_moves:
            continue
        if m_id == "grassyglide" and not has_grassy_surge:
            continue

        if m_id in TWO_TURN_CHARGE_MOVES:
            if m_id == "electroshot" and "Rain" not in team_weathers and not power_herb_available:
                continue
            if m_id in ["solarbeam", "solarblade"] and "Sun" not in team_weathers and not power_herb_available:
                continue
            if m_id not in ["electroshot", "solarbeam", "solarblade"] and not power_herb_available:
                continue

        if m_id == "earthquake" and has_grassy_surge:
            for alt_ground in ["highhorsepower", "stompingtantrum"]:
                if alt_ground in learnset and alt_ground in legal_moves:
                    m_id = alt_ground
                    break
            else:
                continue

        m_info = legal_moves[m_id]
        m_name = m_info["name"]
        if m_name in chosen_moves:
            continue

        if is_physical_set and m_info["category"] == "Special" and m_id not in ["icywind", "electroweb", "snarl", "voltswitch"]:
            continue
        if not is_physical_set and m_info["category"] == "Physical" and m_id not in ["fakeout", "uturn", "knockoff"]:
            continue

        m_type = m_info.get("type", "")
        is_prio = m_info.get("priority", 0) > 0
        if m_info["category"] in ["Physical", "Special"] and not is_prio:
            if m_type in attacking_types_used:
                continue
            attacking_types_used.add(m_type)

        chosen_moves.append(m_name)

    if len(chosen_moves) < 4 and learnset:
        if is_doubles and "protect" in learnset and "protect" in legal_moves and "Protect" not in chosen_moves:
            chosen_moves.append("Protect")

        scored = []
        for m_id in learnset:
            if (
                m_id in BANNED_RECHARGE_MOVES
                or m_id not in legal_moves
                or (m_id == "raindance" and has_fire_sweepers)
                or (m_id == "sunnyday" and has_water_sweepers)
                or (m_id == "fakeout" and has_psychic_terrain)
                or (m_id == "earthquake" and has_grassy_surge)
                or (m_id == "trickroom" and (not wants_trick_room or current_tr_setters_count >= 2))
                or (m_id == "tailwind" and wants_trick_room)
                or (m_id == "grassyglide" and not has_grassy_surge)
                or (m_id == "bodypress" and "Belly Drum" in chosen_moves)
                or m_id in TWO_TURN_CHARGE_MOVES
            ):
                continue
            m_info = legal_moves[m_id]
            if m_info["name"] in chosen_moves:
                continue
            bp = m_info.get("basePower", 0)
            score = 0.0
            if m_info["category"] == target_category and bp >= 55:
                score = bp * (1.5 if m_info["type"] in poke_types else 1.0)
                if m_info.get("priority", 0) > 0:
                    score += 40.0
            elif m_id in ["partingshot", "helpinghand", "taunt", "recover", "yawn", "thunderwave", "lightscreen", "reflect"]:
                score = 90.0
            if score > 0:
                scored.append((score, m_info["name"]))

        scored.sort(reverse=True)
        for _, m_name in scored:
            if len(chosen_moves) >= 4:
                break
            if m_name not in chosen_moves:
                chosen_moves.append(m_name)

    # 5. Asignación de Ítems (Unicidad estricta sin duplicados)
    has_status_move = any(
        legal_moves.get(normalize_id(mv), {}).get("category") == "Status" for mv in chosen_moves
    )
    has_sound_move = any(normalize_id(mv) in SOUND_MOVES for mv in chosen_moves)
    has_charge_move = any(normalize_id(mv) in TWO_TURN_CHARGE_MOVES for mv in chosen_moves)
    move_types = {legal_moves.get(normalize_id(mv), {}).get("type") for mv in chosen_moves}

    # Z-Move Clause
    if assign_z_crystal and not final_item and mech.get("allow_z_moves"):
        lead_type = poke_types[0] if poke_types else "Normal"
        for mv in chosen_moves:
            m_t = legal_moves.get(normalize_id(mv), {}).get("type")
            if m_t in poke_types:
                lead_type = m_t
                break
        cand_z = Z_CRYSTALS_BY_TYPE.get(lead_type)
        if cand_z and normalize_id(cand_z) in legal_items:
            final_item = cand_z

    if not final_item:
        if has_charge_move and "Rain" not in team_weathers and "Sun" not in team_weathers and power_herb_available:
            final_item = "Power Herb"

        if not final_item:
            # --- NUEVO SISTEMA HÍBRIDO DE SINERGIA DE ÍTEMS ---
            scored_items = []
            for it_raw, weight in chaos_data.get("items", {}).items():
                it_id = normalize_id(it_raw)
                if it_id == "nothing" or it_id not in legal_items:
                    continue
                
                score = float(weight)
                it_obj = legal_items[it_id]
                it_name = it_obj["name"]

                # Sinergias de Campos
                req_terrain = TERRAIN_DEPENDENT_ITEMS.get(it_name)
                if req_terrain and req_terrain in team_terrains:
                    score += 0.25  # Empuje táctico moderado si el campo está activo
                    if chosen_ability == "Unburden":
                        score += 2.0  # Empuje masivo (fuerza el combo casi al 100%)
                
                scored_items.append((score, it_id, it_name, it_obj))
            
            # Ordenamos por nuestro nuevo puntaje en lugar del porcentaje puro
            scored_items.sort(key=lambda x: x[0], reverse=True)

            for score, it_id, it_name, it_obj in scored_items:
                if it_obj.get("megaStone") or it_obj.get("isZ") or it_id.endswith("iumz"):
                    continue

                # Control estricto de unicidad
                if it_name == "Leftovers":
                    if mech["item_clause"] and "Leftovers" in used_items:
                        continue
                    if leftovers_count >= 2:
                        continue
                elif it_name in used_items:
                    continue

                if it_name == "Charcoal" and "Fire" not in move_types:
                    continue
                if it_name == "Miracle Seed" and "Grass" not in move_types:
                    continue
                if it_name == "Mystic Water" and "Water" not in move_types:
                    continue

                req_terrain = TERRAIN_DEPENDENT_ITEMS.get(it_name)
                if req_terrain and req_terrain not in team_terrains:
                    continue
                if it_name == "Throat Spray" and not has_sound_move:
                    continue
                if it_name == "Booster Energy" and chosen_ability not in ["Protosynthesis", "Quark Drive"]:
                    continue
                if it_name == "Assault Vest" and has_status_move:
                    continue
                if it_obj.get("isChoice") and has_status_move:
                    continue

                final_item = it_name
                break

        if not final_item:
            # Lista de emergencia ordenada por prioridad (Sitrus primero)
            fallback_priority = [
                "Sitrus Berry", "Leftovers", "Life Orb", "Focus Sash", "Assault Vest", 
                "Safety Goggles", "Rocky Helmet", "Lum Berry", "Covert Cloak", "Clear Amulet"
            ]
            for fb_name in fallback_priority:
                # Buscamos si el ítem existe en la base de datos de esta regulación
                fb_id = normalize_id(fb_name)
                if fb_id in legal_items:
                    if fb_name == "Leftovers":
                        if mech["item_clause"] and "Leftovers" in used_items: continue
                        if leftovers_count >= 2: continue
                    elif fb_name in used_items: continue
                    
                    if fb_name == "Assault Vest" and has_status_move: continue
                    
                    final_item = fb_name
                    break

        # Salvaguarda final: buscar cualquier ítem legal no usado antes de repetir
        if not final_item:
            for it_id, it_obj in legal_items.items():
                if it_obj.get("megaStone") or it_obj.get("isZ") or it_id.endswith("iumz"):
                    continue
                nm = it_obj["name"]
                if nm not in used_items:
                    final_item = nm
                    break

        final_item = final_item or "Sitrus Berry"

    if final_item == "Leftovers":
        leftovers_count += 1

    used_items.add(final_item)
    role_label = compute_accurate_role_label(poke_entry, chosen_ability, chosen_moves, evs, WEATHER_ABILITIES)

    final_stats = calculate_level_50_stats(norm_bs, evs, nature)
    defensive_matchups = compute_defensive_matchups(poke_entry["types"], chosen_ability)

    if wants_perish_trap and "perishsong" in (learnset or []) and "perishsong" in legal_moves \
            and set(poke_entry.get("abilities", [])) & {"Shadow Tag", "Arena Trap", "Magnet Pull"} \
            and not any(normalize_id(m) == "perishsong" for m in chosen_moves):
        chosen_moves.insert(0, legal_moves["perishsong"].get("name", "Perish Song"))

    chosen_moves = dedupe_protect_moves(chosen_moves, learnset, legal_moves, poke_entry)
    top_4_moves = chosen_moves[:4]
    
    rich_details = {
        "item_desc": get_item_description_es(final_item, poke_entry.get("baseSpecies", poke_entry["name"]), gen_num),
        "ability_desc": get_ability_description_es(chosen_ability, gen_num),
        "nature_desc": get_nature_description_es(nature),
        "moves_info": [get_move_rich_details(mv, legal_moves, gen_num) for mv in top_4_moves],
    }

    display_species = poke_entry["name"]
    if base_key == "zacian" and final_item == "Rusted Sword":
        display_species = "Zacian-Crowned"
    elif base_key == "zamazenta" and final_item == "Rusted Shield":
        display_species = "Zamazenta-Crowned"

    return {
        "species": display_species,
        "types": poke_entry["types"],
        "item": final_item,
        "ability": chosen_ability,
        "tera_type": poke_entry["types"][0] if mech.get("allow_tera") else None,
        "nature": nature,
        "evs": evs,
        "ev_source": ev_source,
        "moves": top_4_moves,
        "role": role_label,
        "sprite_url": build_showdown_sprite_url(poke_entry),
        "base_stats": norm_bs,
        "final_stats": final_stats,
        "defensive_matchups": defensive_matchups,
        "details": rich_details,
    }, leftovers_count


def apply_meta_spreads(
    final_team: List[Dict[str, Any]],
    entries: List[Dict[str, Any]],
    team_weathers: Set[str],
) -> None:
    team_move_ids = [{normalize_id(m) for m in (c.get("moves") or [])} for c in final_team]
    team_tailwind = any("tailwind" in s for s in team_move_ids)
    team_tr = any("trickroom" in s for s in team_move_ids)

    for card, entry in zip(final_team, entries):
        if not isinstance(card, dict) or "base_stats" not in card:
            continue
        if card.get("ev_source") == "usage":
            card["ev_plan"] = {"source": "usage"}
            continue
        try:
            moves_info = (card.get("details") or {}).get("moves_info") or []
            evs, nature, plan = plan_spread(
                base_stats=card["base_stats"],
                moves_info=moves_info,
                item=card.get("item") or "",
                ability=card.get("ability") or "",
                team_tailwind=team_tailwind,
                team_tr=team_tr,
                team_weathers=team_weathers,
            )
        except Exception as exc:
            logger.warning(f"Planificador de EVs omitido para {card.get('species')}: {exc}")
            continue

        card["evs"] = evs
        card["nature"] = nature
        card["final_stats"] = calculate_level_50_stats(card["base_stats"], evs, nature)
        card["role"] = compute_accurate_role_label(entry, card.get("ability"), card.get("moves", []), evs, WEATHER_ABILITIES)
        if isinstance(card.get("details"), dict):
            card["details"]["nature_desc"] = get_nature_description_es(nature)
        card["ev_plan"] = plan


def _modern_chart() -> Dict[str, Any]:
    from src.api.routes_analyzer import TYPE_CHART
    return TYPE_CHART


def apply_era_mechanics(final_team: List[Dict[str, Any]], gen: int) -> None:
    if gen >= 6:
        return
    chart = type_chart_for_gen(_modern_chart(), gen)
    for card in final_team:
        types = era_types(card.get("types") or [], gen)
        card["types"] = types
        card["tera_type"] = None
        ability = card.get("ability") or "" if gen >= 3 else ""
        card["defensive_matchups"] = defensive_matchups_for_gen(types, ability, chart, gen)
        if gen <= 2:
            card["ability"] = None
            card["nature"] = None
            card["evs"] = {}
            if gen == 1:
                card["item"] = None
            card["final_stats"] = calc_stats_gen12(card.get("base_stats") or {}, gen)
            card["stat_level"] = 100
            card["ev_plan"] = {"source": "classic"}
            details = card.get("details")
            if isinstance(details, dict):
                details["ability_desc"] = ""
                details["nature_desc"] = ""
                if gen == 1:
                    details["item_desc"] = ""


def build_balanced_synergistic_team(
    ai_species_list: List[str],
    requested_pokes: List[Dict[str, Any]],
    meta_pool: List[Dict[str, Any]],
    pool: Dict[str, Any],
    live_chaos: Dict[str, Any],
    smogon_sets: Dict[str, Any],
    user_prompt: str,
    reserved_items: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    legal_pokemon = pool["legal_pokemon"]
    mech = pool["mechanics"]
    intent = parse_tactical_intent(user_prompt)

    effective_max_megas = 2 if (intent["wants_2_megas"] and mech["allow_megas"]) else mech["max_megas"]
    force_mega_clause = mech.get("force_mega", False) and effective_max_megas >= 1 and not intent.get("wants_no_mega")
    force_restricted_clause = mech.get("force_restricted", False)
    max_restricted = mech.get("max_restricted", 0)

    chosen_entries: List[Dict[str, Any]] = []
    used_bases: Set[str] = set()
    type_counts: Dict[str, int] = {}
    mega_count = 0
    restricted_count = 0
    pure_phys_sweepers = 0
    pure_spec_sweepers = 0
    active_setter_weather: Optional[str] = None

    def is_pivot_or_support(entry: Dict[str, Any]) -> bool:
        ab_set = set(entry.get("abilities", []))
        b_name = normalize_id(entry["baseSpecies"])
        return bool(
            ab_set.intersection({"Intimidate", "Grassy Surge", "Psychic Surge", "Hospitality", "Prankster", "Friend Guard", "Regenerator", "Drizzle", "Drought"})
            or b_name in {"incineroar", "rillaboom", "indeedeef", "sinistcha", "amoonguss", "grimmsnarl", "whimsicott", "pelipper", "tornadus", "klefki"}
        )

    def can_add_entry(entry: Dict[str, Any], strict_balance: bool = True) -> bool:
        nonlocal mega_count, restricted_count, pure_phys_sweepers, pure_spec_sweepers, active_setter_weather
        if entry["baseSpecies"] in used_bases:
            return False
            
        # --- NUEVO: Filtro Anti-Megas Inventadas (Garantiza que tengan su Megapiedra oficial) ---
        if entry.get("is_mega"):
            has_stone = False
            for it_obj in pool["legal_items"].values():
                if it_obj.get("megaStone") and normalize_id(it_obj["megaStone"]) in [normalize_id(entry["baseSpecies"]), normalize_id(entry["name"])]:
                    has_stone = True
                    break
            if not has_stone:
                return False  # ¡Bloquea alucinaciones como Mega Dragonite!
                
        if entry.get("is_mega") and (not mech["allow_megas"] or mega_count >= effective_max_megas):
            return False
        if entry.get("is_restricted") and restricted_count >= max_restricted and max_restricted > 0:
            return False

        # Matriz Antagónica de Climas
        entry_weather = None
        for ab in entry.get("abilities", []):
            if ab in WEATHER_ABILITIES:
                entry_weather = WEATHER_ABILITIES[ab]
                break

        if entry_weather:
            if active_setter_weather and entry_weather != active_setter_weather:
                if not (intent["wants_rain"] and intent["wants_sun"]):
                    return False

        b_name = normalize_id(entry["baseSpecies"])
        bs = entry.get("baseStats", {})
        is_phys = bs.get("atk", 80) >= bs.get("spa", 80)
        is_sup = is_pivot_or_support(entry) and not entry.get("is_mega")

        if intent["wants_tr"]:
            if bs.get("spe", 80) >= 105 and b_name not in TR_SETTERS and b_name not in ["incineroar", "amoonguss"]:
                return False

        if strict_balance:
            for t in entry.get("types", []):
                if type_counts.get(t, 0) >= 2:
                    return False
            if not is_sup:
                if is_phys and pure_phys_sweepers >= 2:
                    return False
                if not is_phys and pure_spec_sweepers >= 2:
                    return False

        chosen_entries.append(entry)
        used_bases.add(entry["baseSpecies"])
        for t in entry.get("types", []):
            type_counts[t] = type_counts.get(t, 0) + 1
        if entry.get("is_mega"):
            mega_count += 1
        if entry.get("is_restricted"):
            restricted_count += 1
        if entry_weather:
            active_setter_weather = entry_weather
        if not is_sup:
            if is_phys:
                pure_phys_sweepers += 1
            else:
                pure_spec_sweepers += 1
        return True

    # 1. Peticiones directas
    for req_p in requested_pokes:
        can_add_entry(req_p, strict_balance=False)

    # 2. Restringidos obligatorios en Ubers
    if force_restricted_clause and restricted_count < max_restricted:
        restricted_candidates = [
            p for p in meta_pool + list(legal_pokemon.values())
            if p.get("is_restricted") and p["baseSpecies"] not in used_bases
        ]
        for r_cand in restricted_candidates:
            if restricted_count >= max_restricted or len(chosen_entries) >= 6:
                break
            can_add_entry(r_cand, strict_balance=False)

    # 3. Arquetipos tácticos
    if intent["wants_tr"]:
        if (intent["wants_mega"] or force_mega_clause) and mega_count < effective_max_megas:
            for m_key in ["cameruptmega", "abomasnowmega", "ampharosmega", "sableyemega", "mawilemega"]:
                if m_key in legal_pokemon:
                    can_add_entry(legal_pokemon[m_key], strict_balance=False)
                    break

        setters_picked = 0
        for tr_setter_id in ["farigiraf", "indeedeef", "hatterene", "sinistcha", "porygon2", "dusclops", "bronzong"]:
            if setters_picked >= 2:
                break
            if tr_setter_id in legal_pokemon and tr_setter_id not in used_bases:
                if can_add_entry(legal_pokemon[tr_setter_id], strict_balance=False):
                    setters_picked += 1

        for tr_abuser_id in ["ursaluna", "torkoal", "kingambit", "amoonguss", "ironhands", "conkeldurr"]:
            if len(chosen_entries) >= 5:
                break
            if tr_abuser_id in legal_pokemon and tr_abuser_id not in used_bases:
                can_add_entry(legal_pokemon[tr_abuser_id], strict_balance=False)

    elif intent["wants_rain"]:
        for r_setter in ["pelipper", "politoed"]:
            if r_setter in legal_pokemon:
                can_add_entry(legal_pokemon[r_setter], strict_balance=False)
                break
        for r_abuser in ["archaludon", "basculegion", "urshifurapidstrike"]:
            if r_abuser in legal_pokemon:
                can_add_entry(legal_pokemon[r_abuser], strict_balance=False)
                break

    if intent["wants_perish_trap"]:
        def _trap_score(e: Dict[str, Any]) -> int:
            return (2 if set(e.get("abilities", [])) & {"Shadow Tag", "Arena Trap", "Magnet Pull"} else 0) + \
                   (2 if "perishsong" in full_learnset(e) else 0)

        trappers = sorted(
            (e for e in legal_pokemon.values() if isinstance(e, dict) and not e.get("is_mega") and _trap_score(e) >= 4),
            key=lambda e: -e.get("bst", 0),
        )
        added_traps = 0
        for e in trappers:
            if added_traps >= 2 or len(chosen_entries) >= 4:
                break
            if can_add_entry(e, strict_balance=False):
                added_traps += 1

    # 4. Candidatos de la IA
    for sp_raw in ai_species_list:
        if len(chosen_entries) >= 6:
            break
        cand = resolve_species_name(sp_raw, _dex_cache(), legal_pokemon)
        if cand and cand.get("is_mega") and (not mech["allow_megas"] or mega_count >= effective_max_megas):
            cand = legal_pokemon.get(normalize_id(cand["baseSpecies"]))
        if cand:
            can_add_entry(cand, strict_balance=True)
    # Segunda pasada: lo que la IA eligió prevalece sobre el relleno automático del meta
    for sp_raw in ai_species_list:
        if len(chosen_entries) >= 6:
            break
        cand = resolve_species_name(sp_raw, _dex_cache(), legal_pokemon)
        if cand and not cand.get("is_mega"):
            can_add_entry(cand, strict_balance=False)

    # 5. Forzar exactamente 1 Mega si no se eligió
    if force_mega_clause and mega_count == 0 and len(chosen_entries) < 6:
        mega_candidates = [
            p for p in meta_pool + list(legal_pokemon.values())
            if p.get("is_mega") and p["baseSpecies"] not in used_bases
        ]
        for m_cand in mega_candidates:
            if can_add_entry(m_cand, strict_balance=True):
                break
        if mega_count == 0:
            for m_cand in mega_candidates:
                if can_add_entry(m_cand, strict_balance=False):
                    break

    # 6. Completar slots restantes
    for fallback_p in meta_pool:
        if len(chosen_entries) >= 6:
            break
        can_add_entry(fallback_p, strict_balance=True)

    for fallback_p in meta_pool:
        if len(chosen_entries) >= 6:
            break
        can_add_entry(fallback_p, strict_balance=False)

    # 6b. Mecánica exclusiva: si el formato permite Megas, el equipo debe llevar al menos una
    if force_mega_clause and mega_count == 0 and chosen_entries:
        def _mega_ok(m: Dict[str, Any]) -> bool:
            return any(
                it.get("megaStone") and normalize_id(it["megaStone"]) in (normalize_id(m["baseSpecies"]), normalize_id(m["name"]))
                for it in pool["legal_items"].values()
            ) and not m.get("is_restricted")

        def _bst(m: Dict[str, Any]) -> int:
            return sum((m.get("baseStats") or {}).values())

        def _swap(i: int, m: Dict[str, Any]) -> None:
            nonlocal mega_count
            for t in chosen_entries[i].get("types", []):
                type_counts[t] = type_counts.get(t, 0) - 1
            used_bases.discard(chosen_entries[i]["baseSpecies"])
            chosen_entries[i] = m
            used_bases.add(m["baseSpecies"])
            for t in m.get("types", []):
                type_counts[t] = type_counts.get(t, 0) + 1
            mega_count += 1

        megas = [m for m in legal_pokemon.values() if m.get("is_mega") and _mega_ok(m)]
        # (a) convertir un miembro que ya está en el equipo a su forma Mega (no cambia la composición)
        conv = [
            (i, m) for i, e in enumerate(chosen_entries[:6]) for m in megas
            if normalize_id(m["baseSpecies"]) == normalize_id(e["baseSpecies"])
        ]
        if conv:
            i, m = max(conv, key=lambda im: _bst(im[1]))
            _swap(i, m)
        else:
            # (b) sustituir al último miembro que NO fue pedido por el usuario por la mejor Mega disponible
            req_ids = {normalize_id(r.get("name", "")) for r in requested_pokes if isinstance(r, dict)}
            free = [i for i in range(len(chosen_entries[:6]) - 1, -1, -1)
                    if normalize_id(chosen_entries[i]["name"]) not in req_ids]
            pool_order = {normalize_id(p.get("name", "")): n for n, p in enumerate(meta_pool)}
            cands = sorted((m for m in megas if m["baseSpecies"] not in used_bases),
                           key=lambda m: (pool_order.get(normalize_id(m["name"]), 10**6), -_bst(m)))
            if free and cands:
                _swap(free[0], cands[0])

    team_weathers: Set[str] = set()
    team_terrains: Set[str] = set()
    for e in chosen_entries[:6]:
        for ab in e.get("abilities", []):
            if ab in WEATHER_ABILITIES:
                team_weathers.add(WEATHER_ABILITIES[ab])
            if ab in TERRAIN_ABILITIES:
                team_terrains.add(TERRAIN_ABILITIES[ab])

    has_fire_sweepers = any("Fire" in e.get("types", []) or "Solar Power" in e.get("abilities", []) for e in chosen_entries[:6])
    has_water_sweepers = any("Water" in e.get("types", []) or "Swift Swim" in e.get("abilities", []) for e in chosen_entries[:6])

    # 7. Asignar exactamente 1 Cristal Z en Gen 7
    gen_num = int(mech.get("gen", 9) or 9)
    force_z_move = mech.get("force_z_move", False) or mech.get("allow_z_moves", False) or (gen_num == 7)
    z_user_idx = -1
    if force_z_move:
        for idx, entry in enumerate(chosen_entries[:6]):
            b_k = normalize_id(entry["baseSpecies"])
            if not entry.get("is_mega") and b_k not in MANDATORY_FORM_ITEMS and not entry.get("requiredItem"):
                z_user_idx = idx
                break

    used_items: Set[str] = set(reserved_items or [])  # objetos de Pokémon que no se tocan
    final_team: List[Dict[str, Any]] = []
    current_tr_setters = 0
    leftovers_count = 0

    for idx, entry in enumerate(chosen_entries[:6]):
        p_set, leftovers_count = extract_live_set_for_pokemon(
            poke_entry=entry,
            pool=pool,
            live_chaos=live_chaos,
            smogon_sets=smogon_sets,
            used_items=used_items,
            team_weathers=team_weathers,
            team_terrains=team_terrains,
            wants_trick_room=intent["wants_tr"],
            current_tr_setters_count=current_tr_setters,
            has_fire_sweepers=has_fire_sweepers,
            has_water_sweepers=has_water_sweepers,
            wants_perish_trap=intent["wants_perish_trap"],
            assign_z_crystal=(idx == z_user_idx),
            leftovers_count=leftovers_count,
        )
        if "Trick Room" in p_set["moves"]:
            current_tr_setters += 1
        final_team.append(p_set)

    sanitize_team_protects(final_team)
    gen_num = int(mech.get("gen", 9) or 9)
    if gen_num >= 3:
        apply_meta_spreads(final_team, chosen_entries[:6], team_weathers)
    apply_era_mechanics(final_team, gen_num)
    return final_team