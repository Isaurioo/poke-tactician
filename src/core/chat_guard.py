"""
Guarda de legalidad para los textos que redacta el LLM en el chat.

El LLM redacta, pero NO es la fuente de verdad: todo lo que cite se contrasta con el motor del formato.
Detecta (y devuelve como etiquetas) lo que el texto RECOMIENDA y no es legal en el formato:
  - especies / Megas (con el mismo resolvedor que usa el generador de equipos)
  - movimientos y objetos que no están en el pool del formato (p. ej. movimientos de Gen 5+ en un formato de Gen 4)
  - mecánicas no permitidas (Mega, Teracristal, Movimientos Z, Dinamax)

Diseño conservador (precisión > cobertura) para no producir falsos positivos en la charla normal:
  - las frases con negación o con una afirmación de ilegalidad se ignoran ("aquí no hay Megas");
  - los nombres sueltos y cortos (palabras comunes) no se buscan: solo nombres compuestos o de >= 8 letras;
  - los nombres en español/francés deben ir con inicial mayúscula (así se escriben los movimientos/objetos);
  - cualquier error interno => no se marca nada (falla abierto, nunca bloquea la charla).
"""
import re
import unicodedata
from typing import Any, Dict, List, Optional, Pattern, Tuple

from src.core.entity_extraction import norm_text, resolve_requests
from src.core.text_validator import DYNA_RE, MEGA_RE, TERA_RE, Z_RE, sentences

# Negación / afirmación de que algo NO está disponible: esa frase no es una recomendación.
_NEG_RE = re.compile(
    r"\b(?:no|sin|nunca|ni|not|never|cannot|can't|isn't|aren't|without|pas|aucun|aucune|non|jamais|"
    r"banned|illegal|unavailable|prohibid\w*|banead\w*|prohib\w*|interdit\w*|banni\w*)\b|n['’]",
    re.I,
)

_CACHE: Dict[str, Dict[str, Any]] = {}


def _fold(s: str) -> str:
    """Quita acentos conservando mayúsculas/minúsculas."""
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")


def _compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _fold(s).lower())


def _searchable(name: str) -> bool:
    """Solo nombres distintivos: compuestos (espacio/guion) o de >= 8 letras. Evita palabras comunes sueltas."""
    n = _fold(name).strip()
    return bool(n) and (" " in n or "-" in n or len(_compact(n)) >= 8)


def _title_rx(names: List[str]) -> Optional[Pattern]:
    """Nombres es/fr: primera letra en mayúscula (estricta) y el resto sin distinguir mayúsculas."""
    parts = []
    for n in sorted({_fold(x).strip() for x in names if x}, key=len, reverse=True):
        parts.append(re.escape(n[0].upper()) + "(?i:" + re.escape(n[1:]) + ")")
    return re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(parts)) if parts else None


def _plain_rx(names: List[str]) -> Optional[Pattern]:
    parts = [re.escape(_fold(x).strip()) for x in sorted({x for x in names if x}, key=len, reverse=True)]
    return re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(parts), re.I) if parts else None


def _legal_names(kind: str, db: Dict[str, Any], legal: Dict[str, Any], i18n: Dict[str, Any]) -> set:
    names = set()
    for k in legal:
        names.add(_compact(k))
        names.add(_compact((db.get(k) or {}).get("name", "")))
        for lang in ("es", "fr"):
            names.add(_compact(((i18n.get(kind) or {}).get(k) or {}).get(lang, "")))
    names.discard("")
    return names


def _build(kind: str, db: Dict[str, Any], legal: Dict[str, Any], i18n: Dict[str, Any], legal_names: set) -> Dict[str, Any]:
    """Nombres (en/es/fr) de lo que EXISTE en la base pero NO es legal en este formato.
    `legal_names` agrupa lo legal de movimientos Y objetos: un nombre que sea legal en cualquiera de los dos se omite."""
    label_of: Dict[str, str] = {}
    en_names: List[str] = []
    loc_names: List[str] = []
    for mid, v in db.items():
        if mid in legal or not isinstance(v, dict) or not v.get("name"):
            continue
        en = v["name"]
        if _compact(en) not in legal_names and _searchable(en):
            en_names.append(en)
            label_of[_compact(en)] = en
        tr = (i18n.get(kind) or {}).get(mid) or {}
        for lang in ("es", "fr"):
            nm = tr.get(lang)
            # un nombre traducido que coincide con uno legal (o con el inglés) no es fiable: se omite
            if nm and _compact(nm) not in legal_names and _searchable(nm):
                loc_names.append(nm)
                label_of[_compact(nm)] = en
    return {"en": _plain_rx(en_names), "loc": _title_rx(loc_names), "label": label_of}


def _matchers(pool: Dict[str, Any]) -> Dict[str, Any]:
    from src.services import format_engine as fe
    from src.services import pokedex_service as pds

    fid = str((pool.get("format") or {}).get("id") or "")
    if fid and fid in _CACHE:
        return _CACHE[fid]
    pds._load_compendium_files()
    i18n = getattr(pds, "_I18N", {}) or {}
    lm, li = pool.get("legal_moves", {}), pool.get("legal_items", {})
    legal_names = _legal_names("moves", fe.MOVES_DB, lm, i18n) | _legal_names("items", fe.ITEMS_DB, li, i18n)
    # Movimientos/objetos LEGALES cuyo nombre contiene "Mega ..." (Mega Punch, Mega Drain): no son la mecánica Mega
    mega_named = [v.get("name") for d in (lm, li) for v in d.values() if isinstance(v, dict) and v.get("name") and MEGA_RE.search(v["name"])]
    built = {
        "moves": _build("moves", fe.MOVES_DB, lm, i18n, legal_names),
        "items": _build("items", fe.ITEMS_DB, li, i18n, legal_names),
        "strip": _plain_rx(mega_named),
    }
    if fid:
        _CACHE[fid] = built
    return built


def _hits(rx_group: Dict[str, Any], text: str) -> List[str]:
    folded = _fold(text)
    out: List[str] = []
    for key in ("en", "loc"):
        rx = rx_group.get(key)
        if rx:
            for m in rx.finditer(folded):
                lab = rx_group["label"].get(_compact(m.group(0)))
                if lab and lab not in out:
                    out.append(lab)
    return out


def find_illegal_mentions(text: str, pool: Dict[str, Any], cache: Dict[str, Any], legal_pokes: Dict[str, Any]) -> List[str]:
    """Etiquetas de lo que `text` recomienda y NO es legal en el formato (lista vacía = nada que corregir)."""
    if not text or not text.strip():
        return []
    labels: List[str] = []
    try:
        # 1) Especies / Megas
        _, bad = resolve_requests(norm_text(text), cache, legal_pokes)
        labels += list(dict.fromkeys(bad))

        mech = pool.get("mechanics", {})
        m = _matchers(pool)
        for sent in sentences(text) or [text]:
            if _NEG_RE.search(sent):  # "aquí no hay Megas", "X no está permitido": no es una recomendación
                continue
            # 2) Mecánicas que el formato no tiene (sin contar movimientos legales llamados "Mega Punch", etc.)
            mech_sent = m["strip"].sub(" ", _fold(sent)) if m.get("strip") else sent
            if not mech.get("allow_megas") and MEGA_RE.search(mech_sent):
                labels.append("Mega Evolution")
            if not mech.get("allow_tera") and TERA_RE.search(mech_sent):
                labels.append("Terastallization")
            if not mech.get("allow_z_moves") and Z_RE.search(mech_sent):
                labels.append("Z-Moves")
            if not mech.get("allow_dynamax") and DYNA_RE.search(mech_sent):
                labels.append("Dynamax/Gigantamax")
            # 3) Movimientos y objetos fuera del pool del formato
            labels += _hits(m["moves"], sent)
            labels += _hits(m["items"], sent)
    except Exception:
        return []  # falla abierto: la guarda nunca debe romper el chat
    return list(dict.fromkeys(labels))
