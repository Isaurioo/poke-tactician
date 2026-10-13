"""Barrera de tema: el asistente solo trata de Pokémon. Se aplica en el servidor, antes y después del modelo."""
import re
import unicodedata
from typing import Optional, Set

_KEYWORDS = {
    "pokemon", "pokémon", "poke", "pokedex", "pokédex", "showdown", "smogon", "vgc", "ou", "uu", "ru", "nu", "pu", "lc", "ubers",
    "equipo", "equipos", "team", "teams", "equipe", "equipes", "competitivo", "competitive", "competitif", "movimiento", "movimientos",
    "move", "moves", "attaque", "attaques", "habilidad", "ability", "talent", "objeto", "item", "objet", "naturaleza", "nature",
    "evs", "ivs", "mega", "megaevolucion", "tera", "teracristalizacion", "dynamax", "gigamax", "zmove", "trick", "tailwind",
    "intimidate", "protect", "tier", "meta", "metajuego", "metagame", "lead", "leads", "sweeper", "wallbreaker", "pivot", "stab",
    "debilidad", "debilidades", "resistencia", "resistencias", "weakness", "resistance", "faiblesse", "tipo", "tipos", "type", "types",
    "formato", "format", "gen", "generacion", "generation", "reg", "doubles", "dobles", "singles", "entrenador", "trainer", "legendario",
    "legendary", "mitico", "mythical", "shiny", "evolucion", "evolution", "evoluciona", "pokeball", "gimnasio", "liga", "champions",
}

_OFFTOPIC = [
    r"\d+\s*[\+\-\*/x×÷\^]\s*\d+",
    r"\b(cu[aá]nto es|how much is|combien font?|calcula|calcular|calculate|calcule|resuelve|solve|r[eé]sous)\b",
    r"```",
    r"\b(def |function\s*\(|console\.log|print\(|#include|public static void|select\s+.+\s+from|import\s+\w+)\b",
    r"\b(escribe|escr[ií]beme|crea|haz|hazme|genera|dame|programa|write|create|make|generate|give me|[eé]cris|cr[eé]e|fais|g[eé]n[eè]re)\b.{0,40}\b(c[oó]digo|code|script|programa|program|funci[oó]n|function|html|css|sql|python|javascript|java|c\+\+|react|api|bot|p[aá]gina web|website|app|aplicaci[oó]n|application)\b",
    r"\b(capital de|capital of|capitale de|qui[eé]n (gan[oó]|es el presidente)|who (won|is the president)|receta|recipe|recette|traduce|translate|traduis|chiste|joke|blague|poema|poem|po[eè]me|ensayo|essay|horoscopo|hor[oó]scopo|weather|m[eé]t[eé]o|bitcoin|criptomoneda|crypto|pol[ií]tica|elecciones|elections?|religi[oó]n|religion|tarea de|homework|devoir|f[uú]tbol|football|soccer|netflix|pel[ií]cula|movie|film|canci[oó]n|song lyrics|letra de)\b",
    r"\b(ignora|olvida|ignore|forget|oublie)\b.{0,30}\b(instrucciones|instructions|reglas|rules|prompt|anteriores|previous)\b",
    r"\b(system prompt|jailbreak|modo desarrollador|developer mode|do anything now|act[uú]a como|act as|pretend to be|finge ser|fais comme si)\b",
]
# Claramente ajenos a Pokémon aunque el mensaje mencione un Pokémon (p. ej. "arma un equipo y suma 2+2")
_HARD = [
    r"```",
    r"\b(system prompt|jailbreak|developer mode|modo desarrollador|do anything now)\b",
    r"\b(ignora|olvida|ignore|forget|oublie)\b.{0,30}\b(instrucciones|instructions|reglas|rules|prompt|anteriores|previous)\b",
    r"\b(cu[aá]nto es|how much is|combien font?|calcula|calculate|calcule|suma|resta|multiplica|divide|add|subtract)\b.{0,12}\d+\s*[\+\-\*/x×÷\^]?\s*\d*",
    r"\b(escribe|crea|haz|genera|dame|write|create|make|generate|[eé]cris|cr[eé]e|fais)\b.{0,40}\b(python|javascript|typescript|java|c\+\+|sql|html|css|react|node\.?js|regex)\b",
]
_HARD_RE = [re.compile(p, re.I | re.S) for p in _HARD]
_OFFTOPIC_RE = [re.compile(p, re.I | re.S) for p in _OFFTOPIC]
_species_cache: Optional[Set[str]] = None


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _species() -> Set[str]:
    global _species_cache
    if _species_cache is None:
        from src.services import pokedex_service as pds
        pds._load_compendium_files()
        names = {_norm(v.get("name", "")) for v in pds._POKEDEX_CACHE.values()}
        # nombres de especie sueltos (>=4 letras) y completos (con guiones/espacios)
        _species_cache = {n for n in names if len(n) >= 4} | {_norm(v.get("baseSpecies", "")) for v in pds._POKEDEX_CACHE.values() if len(v.get("baseSpecies", "")) >= 4}
    return _species_cache


def mentions_pokemon(text: str) -> bool:
    n = _norm(text)
    words = set(re.findall(r"[a-z0-9]+", n))
    if words & {_norm(k) for k in _KEYWORDS}:
        return True
    sp = _species()
    return any(w in sp for w in words)


def looks_off_topic(text: str) -> bool:
    """Descarta antes de llamar al modelo lo claramente ajeno a Pokémon (ahorra tokens y cierra la puerta)."""
    if not text or not text.strip():
        return False
    if any(r.search(text) for r in _HARD_RE):
        return True
    if not any(r.search(text) for r in _OFFTOPIC_RE):
        return False
    return not mentions_pokemon(text)


def reply_is_unsafe(reply: str) -> bool:
    """Última barrera sobre lo que escribe el modelo: nada de código ni de operaciones fuera de tema."""
    return "```" in reply or bool(re.search(r"\b\d+\s*[\+\-\*/x×÷\^]\s*\d+\s*=\s*\d+", reply))
