"""
Extracción de especies del pedido del usuario. Reglas:
  * Solo coincidencias EXACTAS de alias (nombre, forma, Mega, regional y abreviaturas como "landorus-t").
  * Términos tácticos ("versátil", "perish trap", "sweeper"...) nunca se tratan como nombres.
  * La aproximación (typo) es mínima: palabra de 7+ letras a UNA sola letra de distancia y sin ambigüedad.
"""
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

TACTICAL_VOCAB = {
    "versatil", "versatile", "adaptable", "adaptativo", "perish", "trap", "perishtrap", "sweeper", "wallbreaker",
    "stall", "offense", "offensive", "ofensivo", "defensivo", "defensive", "balanced", "balanceado", "balance",
    "hyper", "hyperoffense", "bulky", "setup", "pivot", "support", "soporte", "velocidad", "speed", "coverage",
    "cobertura", "tank", "counter", "core", "lead", "equipo", "genera", "generame", "quiero", "hazme", "armame",
    "crea", "hacer", "para", "con", "sin", "que", "una", "uno", "unos", "unas", "del", "los", "las", "por",
    "formato", "modo", "team", "build", "megas", "megaevolucion", "trick", "room", "tailwind", "rain", "sun",
    "sand", "snow", "lluvia", "sol", "arena", "nieve", "viento", "espacio", "raro", "good", "stuff", "goodstuffs",
    "fast", "slow", "rapido", "lento", "fuerte", "debil", "muros", "muro", "wall", "walls", "protect", "redirect",
    "anti", "contra", "bueno", "mejor", "competitivo", "estrategia", "gen", "ou", "uu", "vgc", "champions",
    "smogon", "singles", "doubles", "dobles", "individual", "ubers", "normal", "terreno", "campo", "clima",
    "equipe", "genere", "construis", "cree", "veux", "besoin", "pluie", "soleil", "sable", "neige", "arriere",
    "distorsion", "offensif", "defensif", "equilibre", "competitif", "strategie", "please", "replace", "change",
    "instead", "remplace", "remplacer", "changer", "cambia", "cambiar", "reemplaza", "mejora", "improve", "ameliore",
}

_FORME_INITIALS = {
    # Therian / Incarnate (Gen 5)
    "therian": ["t"], "incarnate": ["i"], 
    "totem": ["t"], "tótem": ["t"], "totemico": ["t"],
    
    # Formas Regionales
    "alola": ["a", "alolan"], "galar": ["g", "galarian"],
    "hisui": ["h", "hisuian"], "paldea": ["paldean", "p"],
    
    # Origin (Gen 4)
    "origin": ["o"], "origen": ["o"],
    
    # Rotom (Aparatos)
    "wash": ["w"], "lavadora": ["w"], "agua": ["w"],
    "heat": ["h"], "horno": ["h"], "fuego": ["h"],
    "frost": ["f"], "nevera": ["f"], "hielo": ["f"],
    "mow": ["m"], "corte": ["m"], "cortacesped": ["m"], "planta": ["m"],
    "fan": ["s"], "ventilador": ["s"], "volador": ["s"],
    
    # Urshifu (Estilos)
    "rapidstrike": ["rapidstrike"], "rapid": ["rapidstrike"], "fluido": ["rapidstrike"], 
    "agua": ["rapidstrike"], "single": ["singlestrike"], "brusco": ["singlestrike"],
    
    # Ogerpon (Máscaras)
    "wellspring": ["wellspring"], "fuente": ["wellspring"], "agua": ["wellspring"],
    "hearthflame": ["hearthflame"], "horno": ["hearthflame"], "fuego": ["hearthflame"],
    "cornerstone": ["cornerstone"], "piedra": ["cornerstone"], "roca": ["cornerstone"], "cimiento": ["cornerstone"],
}
_PRE_MODS = {"alolan": "alola", "alola": "alola", "galarian": "galar", "galar": "galar",
             "hisuian": "hisui", "hisui": "hisui", "paldean": "paldea", "paldea": "paldea"}

_INDEX_CACHE: Dict[Tuple[int, int], Dict[str, Any]] = {}


def norm_text(s: Any) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _clean(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", norm_text(s))


def build_index(cache: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    ck = (id(cache), len(cache))
    if ck in _INDEX_CACHE:
        return _INDEX_CACHE[ck]
    forms_by_base: Dict[str, List[Dict[str, Any]]] = {}
    by_full: Dict[str, Dict[str, Any]] = {}
    base_display: Dict[str, str] = {}
    for p in cache.values():
        if p.get("num", 0) <= 0:
            continue
        name = p.get("name") or ""
        base = _clean(p.get("baseSpecies") or name)
        forms_by_base.setdefault(base, []).append(p)
        by_full[_clean(name)] = p
        base_display.setdefault(base, p.get("baseSpecies") or name)

    targets: Dict[str, Tuple[str, Optional[str], bool, Optional[str]]] = {b: (b, None, False, None) for b in forms_by_base}
    for full, p in by_full.items():
        base = _clean(p.get("baseSpecies") or p.get("name"))
        if full == base:
            continue
        mega = bool(p.get("is_mega"))
        
        # --- NUEVO CÓDIGO DE RESPALDO PARA FORMAS ---
        raw_forme = p.get("forme")
        if not raw_forme:
            name_str = p.get("name", "")
            base_str = p.get("baseSpecies", "")
            if base_str and name_str.startswith(base_str + "-"):
                raw_forme = name_str[len(base_str)+1:]
        
        forme = norm_text(raw_forme or "")
        # --------------------------------------------
        
        m = re.search(r"mega[- ]?([xy])$", forme)
        variant = m.group(1) if m else None
        targets.setdefault(full, (base, full, mega, variant))
        if mega:
            targets.setdefault("mega" + base + (variant or ""), (base, full, True, variant))
            if variant:
                targets.setdefault(base + variant, (base, full, True, variant))
        else:
            for tok in re.split(r"[-\s]+", forme):
                for ini in _FORME_INITIALS.get(tok, []):
                    targets.setdefault(base + ini, (base, full, False, None))
    for base, forms in forms_by_base.items():
        if any(f.get("is_mega") for f in forms):
            targets.setdefault("mega" + base, (base, None, True, None))
            targets.setdefault(base + "mega", (base, None, True, None))

    idx = {"targets": targets, "forms_by_base": forms_by_base, "by_full": by_full, "base_display": base_display}
    _INDEX_CACHE[ck] = idx
    return idx


def _edit1(a: str, b: str) -> bool:
    """True si a y b difieren en como máximo UNA letra (sustitución, inserción o borrado)."""
    if abs(len(a) - len(b)) > 1:
        return False
    i = j = diffs = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        diffs += 1
        if diffs > 1:
            return False
        if len(a) == len(b):
            i += 1
            j += 1
        elif len(a) > len(b):
            i += 1
        else:
            j += 1
    return diffs + (len(a) - i) + (len(b) - j) <= 1


def _fuzzy(token: str, bases: List[str]) -> Optional[str]:
    if len(token) < 7 or token in TACTICAL_VOCAB or token.isdigit():
        return None
    cands = [b for b in bases if len(b) >= 7 and b[0] == token[0] and _edit1(token, b)]
    return cands[0] if len(cands) == 1 else None


def find_mentions(prompt: str, cache: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    # --- NUEVO TRADUCTOR INSTANTÁNEO DE ALIAS (ES -> EN) ---
    translations = {
        "horno": "heat", "fuego": "heat",
        "lavadora": "wash", "agua": "wash",
        "nevera": "frost", "hielo": "frost",
        "cortacesped": "mow", "corte": "mow", "planta": "mow",
        "ventilador": "fan", "volador": "fan",
        "fluido": "rapidstrike", "brusco": "singlestrike",
        "fuente": "wellspring", "piedra": "cornerstone", "cimiento": "cornerstone"
    }
    for es_word, en_word in translations.items():
        # Reemplaza la palabra en español por el sufijo oficial en inglés antes de analizar
        prompt = re.sub(rf"\b{es_word}\b", en_word, prompt, flags=re.IGNORECASE)
    # ---------------------------------------------------------

    idx = build_index(cache)
    targets = idx["targets"]
    bases = list(idx["forms_by_base"])
    tokens = re.findall(r"[a-z0-9]+", norm_text(prompt))
    
    # ... (el resto del código sigue igual hacia abajo)    idx = build_index(cache)
    found: Dict[str, Dict[str, Any]] = {}
    i = 0
    while i < len(tokens):
        hit = None
        if tokens[i] not in TACTICAL_VOCAB or tokens[i] == "mega":
            for n in (3, 2, 1):
                if i + n <= len(tokens):
                    phrase = "".join(tokens[i:i + n])
                    if phrase in targets:
                        hit = (n, targets[phrase], False)
                        break
            if not hit:
                fz = _fuzzy(tokens[i], bases)
                if fz:
                    hit = (1, targets[fz], True)
        if not hit:
            i += 1
            continue
        n, (base, form, mega, variant), fuzzy = hit
        prev = tokens[i - 1] if i > 0 else ""
        nxt = tokens[i + n] if i + n < len(tokens) else ""
        nxt2 = tokens[i + n + 1] if i + n + 1 < len(tokens) else ""
        if not mega:
            if prev == "mega":
                mega = True
            elif nxt == "mega":
                mega, variant = True, (nxt2 if nxt2 in ("x", "y") else None)
            elif nxt in ("megax", "megay"):
                mega, variant = True, nxt[-1]
        elif variant is None and form is None and nxt in ("x", "y"):
            variant = nxt
        pre = _PRE_MODS.get(prev) if (not mega and form is None) else None
        prevm = found.get(base)
        if prevm:
            prevm["mega"] = prevm["mega"] or mega
            prevm["variant"] = prevm["variant"] or variant
            prevm["fuzzy"] = prevm["fuzzy"] and fuzzy
        else:
            found[base] = {"base": base, "form": form, "mega": mega, "variant": variant, "pre": pre, "fuzzy": fuzzy}
        i += n
    return list(found.values())


def _legal_map(legal_pokes: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in legal_pokes.items():
        if isinstance(v, dict):
            out[_clean(k)] = v
            if v.get("name"):
                out.setdefault(_clean(v["name"]), v)
    return out


def resolve_requests(prompt: str, cache: Dict[str, Dict[str, Any]], legal_pokes: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """(entradas legales pedidas, etiquetas de lo pedido que NO es legal en el formato)."""
    idx = build_index(cache)
    legal = _legal_map(legal_pokes)
    entries: List[Dict[str, Any]] = []
    illegal: List[str] = []
    for m in find_mentions(prompt, cache):
        base = m["base"]
        family = idx["forms_by_base"][base]
        disp = idx["base_display"][base]
        pick, label = None, disp
        if m["form"]:
            pick = legal.get(m["form"])
            f = idx["by_full"].get(m["form"])
            if not pick and f:
                label = f"Mega {disp}" + (f" {m['variant'].upper()}" if m["variant"] else "") if f.get("is_mega") else f.get("name", disp)
        elif m["mega"]:
            megas = [f for f in family if f.get("is_mega") and (not m["variant"] or _clean(f.get("name", "")).endswith("mega" + m["variant"]))]
            ok = [legal[_clean(f["name"])] for f in megas if _clean(f["name"]) in legal]
            if ok:
                pick = ok[0]
            else:
                label = f"Mega {disp}" + (f" {m['variant'].upper()}" if m["variant"] else "")
        else:
            cands = [f for f in family if _clean(f["name"]) in legal and not f.get("is_mega")]
            if m["pre"]:
                pc = [f for f in cands if m["pre"] in norm_text(f.get("forme") or "")]
                cands = pc or cands
            base_first = [f for f in cands if (f.get("forme") or "Base") == "Base"]
            src = base_first or cands
            if src:
                pick = legal[_clean(src[0]["name"])]
        if pick:
            if pick not in entries:
                entries.append(pick)
        elif not m["fuzzy"]:                       # lo aproximado nunca provoca un error
            illegal.append(label)
    return entries, illegal


def resolve_species_name(name: str, cache: Dict[str, Dict[str, Any]], legal_pokes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resuelve un nombre propuesto por la IA a una entrada LEGAL del formato (exacto, sin aproximaciones)."""
    legal = _legal_map(legal_pokes)
    key = _clean(name)
    if key in legal:
        return legal[key]
    idx = build_index(cache)
    t = idx["targets"].get(key)
    if not t:
        return None
    base, form, mega, _variant = t
    if form and form in legal:
        return legal[form]
    if mega:
        return None
    for f in idx["forms_by_base"].get(base, []):
        if (f.get("forme") or "Base") == "Base" and _clean(f["name"]) in legal:
            return legal[_clean(f["name"])]
    return None
