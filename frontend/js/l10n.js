/* ==========================================================================
   L10N — nombres y descripciones traducidos de Pokémon, movimientos, objetos y habilidades.
   - Los datos (es / fr) se piden una vez por idioma a /api/compendium/l10n/<lang> y se cachean.
   - El inglés es el idioma canónico de Showdown: no necesita datos.
   - Si falta una traducción, siempre se devuelve el nombre/descripción original.
   ========================================================================== */
(function () {
  const EMPTY = { pokemon: {}, moves: {}, items: {}, abilities: {} };
  const KEY = { pokemon: "pokemon", move: "moves", item: "items", ability: "abilities" };
  const cache = {};
  const pending = {};

  const compact = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const current = () => cache[window.I18N ? I18N.lang : "es"] || EMPTY;

  function isReady(lang) {
    return lang === "en" || !!cache[lang];
  }

  async function load(lang) {
    lang = lang || I18N.lang;
    if (lang === "en") { cache.en = EMPTY; return EMPTY; }
    if (cache[lang]) return cache[lang];
    if (!pending[lang]) {
      pending[lang] = ApiService.getL10n(lang)
        .then((d) => (cache[lang] = d && d.pokemon ? d : EMPTY))   // sin endpoint/datos: se cachea vacío
        .catch(() => (cache[lang] = EMPTY))
        .finally(() => { delete pending[lang]; });
    }
    return pending[lang];
  }

  function entry(kind, id) {
    return (current()[KEY[kind]] || {})[id];
  }

  // nombre a mostrar de un objeto con { id, name }
  function name(kind, o) {
    const e = entry(kind, o.id);
    const n = Array.isArray(e) ? e[0] : e;
    return n || o.name;
  }

  // nombre a mostrar a partir de un nombre en inglés suelto ("Choice Scarf")
  function nameOf(kind, rawName) {
    const e = entry(kind, compact(rawName));
    const n = Array.isArray(e) ? e[0] : e;
    return n || rawName;
  }

  function desc(kind, id) {
    const e = entry(kind, id);
    return Array.isArray(e) ? e[1] || "" : "";
  }

  window.L10N = { load, isReady, name, nameOf, desc };
})();
