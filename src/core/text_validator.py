"""
Validación determinista del texto que escribe la IA. La IA redacta, pero NO es la fuente de verdad:
cada viñeta se contrasta con los datos del motor (tipos de la generación, habilidades legales,
Pokédex del formato, mecánicas permitidas, pivotes del set) y las que fallan se descartan.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.era_rules import effectiveness, norm
from src.core.move_rules import has_pivot

# Nombres de tipo en es / en / fr. Se omiten los ambiguos con palabras comunes (sol, normal...).
TYPE_WORDS: Dict[str, List[str]] = {
    "Fire": ["fuego", "fire", "feu"], "Water": ["agua", "water", "eau"],
    "Electric": ["eléctrico", "electrico", "electric", "électrik", "electrik"],
    "Grass": ["planta", "grass", "plante"], "Ice": ["hielo", "ice", "glace"],
    "Fighting": ["lucha", "fighting", "combat"], "Poison": ["veneno", "poison"],
    "Ground": ["tierra", "ground"], "Flying": ["volador", "flying", "vol"],
    "Psychic": ["psíquico", "psiquico", "psychic", "psy"], "Bug": ["bicho", "bug", "insecte"],
    "Rock": ["roca", "rock", "roche"], "Ghost": ["fantasma", "ghost", "spectre"],
    "Dragon": ["dragón", "dragon"], "Dark": ["siniestro", "dark", "ténèbres", "tenebres"],
    "Steel": ["acero", "steel", "acier"], "Fairy": ["hada", "fairy", "fée"],
}
_TYPE_RX = {t: re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(map(re.escape, ws)), re.I) for t, ws in TYPE_WORDS.items()}

RESIST_RE = re.compile(r"(?:resist\w*|inmun\w*|immun\w*|r[ée]sist\w*)", re.I)
WEAK_RE = re.compile(r"(?:d[ée]bil\w*|weak\w*|faible\w*|vulnerab\w*)", re.I)
HIT_RE = re.compile(r"(?:supereficaz|super[- ]?effective|golpea|conecta|da[ñn]a|afecta|\bhits?\b|connects|touche|frappe)", re.I)
NEG_RE = re.compile(r"\b(?:no|sin|nunca|ni|inmune|inmunidad|falla|not|never|cannot|can't|immune|fails|pas|aucun)\b", re.I)

FAIRY_RE = re.compile(r"(?<!\w)(?:hada|fairy|fée)(?!\w)", re.I)
MEGA_RE = re.compile(r"(?i:megaevol\w*|mega-evol\w*|megapiedra|mega stone)|\bMega[- ][A-Z]")
Z_RE = re.compile(r"cristal(?:es)? z|z-move|movimiento z|cristaux z|capacité z", re.I)
DYNA_RE = re.compile(r"dinamax|dynamax|gigamax|gigantamax", re.I)
TERA_RE = re.compile(r"teracrist\w*|terastal\w*|téracristal\w*|tera type|tipo tera", re.I)
PIVOT_RE = re.compile(r"pivot\w*", re.I)


def types_in(text: str) -> List[str]:
    return [t for t, rx in _TYPE_RX.items() if rx.search(text)]


def sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _name_rx(name: str) -> "re.Pattern":
    return re.compile(r"(?<!\w)%s(?!\w)" % re.escape(name))


def build_context(
    gen: int,
    chart: Dict[str, Dict[str, float]],
    mechanics: Dict[str, Any],
    forbidden_names: List[str],
    species_info: Dict[str, Dict[str, Any]],
    team_moves: List[Dict[str, str]],
    ability_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    species_info: {nombre_base: {"types": [...], "ability": "...", "legal_abilities": [...]}} del equipo y
    de las amenazas candidatas. forbidden_names: especies que NO pueden citarse (anacrónicas / prohibidas).
    """
    names = sorted({n for n in forbidden_names if len(n) >= 4}, key=len, reverse=True)
    forbidden_rx = re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(map(re.escape, names))) if names else None
    ab_names = sorted({a for a in (ability_names or []) if len(a) >= 4}, key=len, reverse=True)
    ability_rx = re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(map(re.escape, ab_names)), re.I) if ab_names else None
    return {
        "ability_rx": ability_rx,
        "gen": gen, "chart": chart, "mechanics": mechanics, "forbidden_rx": forbidden_rx,
        "species": {k: {**v, "rx": _name_rx(k)} for k, v in species_info.items()},
        "team_moves": [{**m, "rx": re.compile(r"(?<!\w)%s(?!\w)" % re.escape(m["move"]), re.I)} for m in team_moves],
    }


def check_line(line: str, ctx: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    gen, chart, mech = ctx["gen"], ctx["chart"], ctx["mechanics"]

    if ctx["forbidden_rx"]:
        m = ctx["forbidden_rx"].search(line)
        if m:
            out.append(f"{m.group(0)} no existe o no es legal en este formato/generación")
    if gen < 6 and FAIRY_RE.search(line):
        out.append("el tipo Hada no existe antes de la Gen 6")
    if not mech.get("allow_megas") and MEGA_RE.search(line):
        out.append("las Megaevoluciones no existen en este formato")
    if gen != 7 and Z_RE.search(line):
        out.append("los Movimientos Z no existen en esta generación")
    if gen != 8 and DYNA_RE.search(line):
        out.append("Dinamax no existe en esta generación")
    if not (gen == 9 and mech.get("allow_tera", True)) and TERA_RE.search(line):
        out.append("la Teracristalización no existe en este formato")

    mentioned = [k for k, info in ctx["species"].items() if info["rx"].search(line)]
    if len(mentioned) == 1:                       # solo se verifica si la viñeta habla de UN Pokémon
        sp = ctx["species"][mentioned[0]]
        legal = {norm(a) for a in sp.get("legal_abilities", [])}
        if gen >= 3 and legal and ctx.get("ability_rx"):
            for m in ctx["ability_rx"].finditer(line):
                if norm(m.group(0)) not in legal:
                    out.append(f"{mentioned[0]} no tiene la habilidad {m.group(0)} en Gen {gen}")
                    break
        for kw_re, kind in ((RESIST_RE, "resist"), (WEAK_RE, "weak")):
            for m in kw_re.finditer(line):
                seg = re.split(r"[.;:]|\bpero\b|\bbut\b|\bmais\b|\baunque\b", line[m.end(): m.end() + 70], maxsplit=1)[0]
                seg = re.split(WEAK_RE if kind == "resist" else RESIST_RE, seg, maxsplit=1)[0]
                for t in types_in(seg):
                    if t not in chart:
                        continue
                    mult = effectiveness(chart, t, sp["types"], sp.get("ability", ""), gen)
                    if (kind == "resist" and mult >= 1.0) or (kind == "weak" and mult <= 1.0):
                        word = "resiste/es inmune a" if kind == "resist" else "es débil a"
                        out.append(f"{mentioned[0]} no {word} {t} (daño real x{mult:g})")

    if HIT_RE.search(line) and not NEG_RE.search(line):
        for mv in ctx["team_moves"]:
            if mv["rx"].search(line):
                for t in types_in(line):
                    if t in chart and effectiveness(chart, mv["type"], [t]) == 0.0:
                        out.append(f"{mv['move']} ({mv['type']}) no afecta a tipo {t}")
    return out


def validate_fields(fields: Dict[str, str], ctx: Dict[str, Any]) -> List[str]:
    problems: List[str] = []
    for text in fields.values():
        for line in str(text).split("\n"):
            for p in check_line(line, ctx):
                if p not in problems:
                    problems.append(p)
    return problems


def sanitize_fields(fields: Dict[str, str], ctx: Dict[str, Any], fallbacks: Dict[str, str]) -> Dict[str, str]:
    """Descarta las viñetas con errores; si un campo se queda vacío usa el texto de respaldo del motor."""
    out: Dict[str, str] = {}
    for key, text in fields.items():
        kept = [ln for ln in str(text).split("\n") if ln.strip() and not check_line(ln, ctx)]
        out[key] = "\n".join(kept) if kept else fallbacks.get(key, "")
    return out


# --------------------------------------------------------------------------- #
# Guía del Creador: coherencia de "pivotea" con los movimientos reales del set
# --------------------------------------------------------------------------- #
def drop_false_pivot_sentences(text: str, team: List[Dict[str, Any]]) -> str:
    """Quita las frases que dicen que un Pokémon 'pivotea' cuando su set no tiene movimiento de pivote."""
    rx_team = [(p, _name_rx(str(p.get("species", "")).split("-")[0])) for p in team]
    kept: List[str] = []
    for s in sentences(text):
        if PIVOT_RE.search(s):
            named = [p for p, rx in rx_team if rx.search(s)]
            if any(not has_pivot(p.get("moves", [])) for p in named):
                continue
        kept.append(s)
    return " ".join(kept)


# --------------------------------------------------------------------------- #
# Guía del Creador: conceptos que no existen en la era del formato
# --------------------------------------------------------------------------- #
_ERA_WORDS = {
    "abilities": r"habilidad\w*|abilit\w+|talent\w*",
    "natures": r"naturalez\w*|\bnatures?\b",
    "evs": r"\bEVs?\b|\bIVs?\b|stat exp|esfuerzo",
    "items": r"\bobjetos?\b|\bitems?\b|\bbayas?\b|\bberry\b|\bchoice\b|leftovers|life orb|focus sash",
}


def drop_era_anachronisms(text: str, era: Dict[str, Any]) -> str:
    """Quita las frases que mencionan habilidades, objetos, naturalezas o EVs en eras que no los tienen."""
    pats = []
    if not era.get("has_abilities", True):
        pats.append(_ERA_WORDS["abilities"])
    if not era.get("has_natures", True):
        pats.append(_ERA_WORDS["natures"])
    if not era.get("modern_evs", True):
        pats.append(_ERA_WORDS["evs"])
    if not era.get("has_items", True):
        pats.append(_ERA_WORDS["items"])
    if not pats:
        return text
    rx = re.compile("|".join(pats), re.I)
    return " ".join(s for s in sentences(text) if not rx.search(s))
