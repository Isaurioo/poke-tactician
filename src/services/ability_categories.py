"""
Clasificación de habilidades por tipo de efecto.

Se basa en el texto de la descripción (español e inglés a la vez) porque ni abilities.json
ni Showdown traen una categoría. Es una heurística: cada habilidad recibe
  - una categoría PRINCIPAL (la que define su color en la interfaz), y
  - hasta dos etiquetas secundarias (otras categorías que también encajan).

El orden de ABILITY_CATEGORIES es la prioridad: gana la primera que coincida.
"""
import re
from typing import Dict, List, Optional, Tuple

# (id, patrón ES, patrón EN)
_RULES: List[Tuple[str, str, str]] = [
    ("forme",
     r"cambia de forma|cambia a (la )?forma|se convierte en|\bforma\b|transforma",
     r"\bforme\b|changes? (its )?form|transforms?|disguise|busted|zen mode"),
    ("weather",
     r"clima|llueva|llueve|lluvia|\bsol\b|soleado|tormenta de arena|arena|granizo|granice|graniza|nieve|nieva|nevada|niebla|terreno|campo (el|de|ps)",
     r"weather|\brain\b|sunny day|harsh sunlight|sandstorm|\bsnow\b|\bhail\b|terrain|\bfog\b|rain dance|desolate land|primordial sea"),
    ("type",
     r"(pasan?|pasen|se vuelven?|se vuelvan?|se convierten?|se convierta[n]?) (a ser )?(de )?tipo|cambia (de|el|su) tipo|cambia a tipo|adopta el tipo|su tipo (cambia|pasa)|de tipo \w+ en vez",
     r"becomes? .{0,25}-type|changes? (its|the|this pokemon's) type|type-changing|moves? (are|become|turn into) .{0,25}-type|-type moves? (become|are)"),
    ("entry",
     r"al entrar (en|al) (el )?(combate|campo)|al salir al (combate|campo)|nada m[aá]s entrar|al entrar en|cuando entra",
     r"on switch-in|when (it|this pokemon) enters|upon entering|enters? a battle|switch in"),
    ("contact",
     r"contacto|tocarlo|lo toque|le toque|al tocar",
     r"\bcontact\b"),
    ("items",
     r"objeto|\bbayas?\b|\bmiel\b|recoger objetos",
     r"\bitem\b|\bberry\b|berries|held item"),
    ("status",
     r"envenen|veneno|paraliz|quemadur|se quema|quemarse|duerm|dormid|sue[ñn]o|congel|confus|enamor|amedrent|problemas de estado|estados? alterados?|alteraci[oó]n de estado|somnolien",
     r"poison|\bburn|paraly|\bsleep|asleep|\bfreeze|frozen|confus|infatuat|flinch|status condition|major status|toxic"),
    ("speed",
     r"velocidad|prioridad|ataca primero|ataque el primero|antes que|tras todos|descansar[aá]",
     r"\bspeed\b|priority|moves? first|go first|act(s)? more slowly"),
    ("defense",
     r"reduc\w+ .{0,30}da[ñn]o|da[ñn]o .{0,25}(recibe|sufre|infligen|inflige el)|recib\w+ da[ñn]o|sufre da[ñn]o|no (recibe|sufre|le afecta|logran)|"
     r"evita|inmun|anula|neutraliza|protege|bloquea|impide|resist|absorbe|aguanta|sobrevive|no puede ser|elude|rechaza|devuelve|refleja|hacen da[ñn]o|no puede da[ñn]arse",
     r"damage (is|taken|received)? ?(reduced|halved)|reduces? (the )?damage|takes? (no|half)|\bimmun|prevent|cannot be|can't be|protects?|resists?|"
     r"only be damaged|nullif|absorbs?|survive|endure|negates?|takes? .{0,20}half"),
    ("healing",
     r"recupera|restaura|\bcura\b|curar|regenera|recuper",
     r"restores?|recovers?|\bheals?\b|regenerat|hp is restored"),
    ("utility",
     r"copia|copiar|adquiere|ignora|habilidades? del objetivo|sorteando|prev[eé]|\bpp\b|alcanzar a pok[eé]mon|reacciona",
     r"copies|ignores?|abilities|ability of"),
    ("offense",
     r"potencia|potencian|potente|mordedura|golpes|m[uú]ltiples|cr[ií]tico|m[aá]s da[ñn]o|da[ñn]o que inflige|da[ñn]o equivalente|ataca dos veces|\bstab\b",
     r"\bpower\b|powers? up|damage dealt|multiplied by|\bstab\b|critical|multi-?hit|hits? (twice|\d)|boosts? the damage"),
    ("stats",
     r"aument|\bsube|suben|sub[ei]\b|refuerza|mejora|\bbaja|disminuy|\bduplica|reduce (su|el|la)",
     r"raises?|boosts?|increases?|lowers?|stage|doubles?"),
]

# Correcciones manuales: habilidades competitivas cuyo texto no permite deducir su categoría.
_OVERRIDES: Dict[str, str] = {
    # inmunidades por absorción / defensivas
    "waterabsorb": "defense", "voltabsorb": "defense", "flashfire": "defense", "lightningrod": "defense",
    "stormdrain": "defense", "sapsipper": "defense", "motordrive": "defense", "dryskin": "defense",
    "eartheater": "defense", "wellbakedbody": "defense", "windrider": "defense", "levitate": "defense",
    "magicbounce": "defense", "magicguard": "defense", "wonderguard": "defense", "rockhead": "defense",
    "innerfocus": "defense", "sturdy": "defense", "multiscale": "defense", "shadowshield": "defense",
    "fluffy": "defense", "furcoat": "defense", "thickfat": "defense", "mirrorarmor": "defense",
    "terashell": "defense", "aurabreak": "utility",
    # ofensivas
    "sheerforce": "offense", "technician": "offense", "adaptability": "offense", "toughclaws": "offense",
    "sharpness": "offense", "strongjaw": "offense", "rockypayload": "offense", "parentalbond": "offense",
    "innardsout": "offense", "skilllink": "offense", "tintedlens": "offense", "hugepower": "offense",
    "purepower": "offense", "gorillatactics": "offense", "hustle": "offense",
    # estados
    "owntempo": "status", "stench": "status", "naturalcure": "status", "poisonheal": "status",
    # tipo / forma
    "protean": "type", "libero": "type", "colorchange": "type", "multitype": "type", "rkssystem": "type",
    "forecast": "forme", "disguise": "forme", "iceface": "forme", "zenmode": "forme", "battlebond": "forme",
    # velocidad
    "stall": "speed", "quickdraw": "speed", "truant": "speed", "myceliummight": "speed",
    # utilidad
    "pressure": "utility", "anticipation": "utility", "frisk": "utility", "telepathy": "utility",
    "moldbreaker": "utility", "teravolt": "utility", "turboblaze": "utility", "infiltrator": "utility",
    "scrappy": "utility", "noguard": "utility", "dancer": "utility", "trace": "utility",
    "receiver": "utility", "powerofalchemy": "utility", "asone": "utility", "runaway": "utility",
    "honeygather": "utility", "forewarn": "utility", "shadowtag": "utility", "arenatrap": "utility",
    "magnetpull": "utility", "neutralizinggas": "utility",
    "liquidooze": "defense",
}

ABILITY_CATEGORIES: List[str] = [r[0] for r in _RULES] + ["passive"]

_COMPILED: Dict[str, Tuple[re.Pattern, re.Pattern]] = {
    cid: (re.compile(es, re.IGNORECASE), re.compile(en, re.IGNORECASE)) for cid, es, en in _RULES
}

_PLACEHOLDER_ES = re.compile(r"^efecto de la habilidad .+ activo en combate\.?$", re.IGNORECASE)
_EN_HINT = re.compile(r"\b(the|its|this pok[eé]mon|pok[eé]mon's|when|if|of)\b", re.IGNORECASE)
_ES_HINT = re.compile(r"\b(el|la|los|las|de|del|que|su|sus|cuando|si|al)\b", re.IGNORECASE)


def is_placeholder(text: Optional[str]) -> bool:
    """Descripciones generadas automáticamente por el script de descarga ('Efecto de la habilidad X activo...')."""
    return bool(text) and bool(_PLACEHOLDER_ES.match(text.strip()))


def looks_english(text: Optional[str]) -> bool:
    """Algunas entradas del campo en español traen el texto original en inglés."""
    if not text:
        return False
    return len(_EN_HINT.findall(text)) >= 2 and len(_ES_HINT.findall(text)) <= 1


def classify(text_es: str = "", text_en: str = "", ability_id: str = "") -> Tuple[str, List[str]]:
    """Devuelve (categoría_principal, [etiquetas_secundarias])."""
    matched: List[str] = []
    for cid, (rx_es, rx_en) in _COMPILED.items():
        if (text_es and rx_es.search(text_es)) or (text_en and rx_en.search(text_en)):
            matched.append(cid)

    forced = _OVERRIDES.get(ability_id)
    if forced:
        tags = [m for m in matched if m != forced][:2]
        return forced, tags
    if not matched:
        return "passive", []
    return matched[0], matched[1:3]
