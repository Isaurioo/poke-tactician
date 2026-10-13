/* ==========================================================================
   COMPENDIO — listado + fichas completas (Pokémon, movimientos, objetos, habilidades)
   - El listado carga /api/compendium (ligero) y filtra/ordena en el cliente.
   - Barra inferior de chips con badges de conteo dinámico en TODAS las pestañas.
   - Sincronización bidireccional entre chips interactivos y selectores dropdown.
   ========================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("compendium-grid");
  if (!grid) return;

  const searchInput = document.getElementById("compendium-search");
  const filter1 = document.getElementById("compendium-subfilter");
  const filter2 = document.getElementById("compendium-subfilter2");
  const sortSel = document.getElementById("compendium-sort");
  const resultsCount = document.getElementById("compendium-results-count");
  const notice = document.getElementById("compendium-notice");
  const sentinel = document.getElementById("compendium-sentinel");
  const tabButtons = document.querySelectorAll(".compendium-tab");

  const modalEl = document.getElementById("compendium-detail-modal");
  const modalHeader = document.getElementById("detail-modal-header");
  const modalBody = document.getElementById("detail-modal-body");
  const backBtn = document.getElementById("detail-back-btn");
  const modal = modalEl ? new bootstrap.Modal(modalEl) : null;

  let data = { pokemon: [], items: [], abilities: [], moves: [] };
  let caps = {};
  let currentTab = "pokemon";
  let viewList = [];
  let renderedCount = 0;
  const PAGE_SIZE = 60;
  const detailStack = [];
  let currentDetail = null;
  let learnersGen9 = true;

  /* ------------------------------------------------------------------ */
  /* Constantes y Paletas Visuales                                      */
  /* ------------------------------------------------------------------ */
  const TYPE_COLORS = {
    normal: "#94a3b8", fire: "#f97316", water: "#38bdf8", electric: "#eab308",
    grass: "#22c55e", ice: "#06b6d4", fighting: "#dc2626", poison: "#a855f7",
    ground: "#d97706", flying: "#818cf8", psychic: "#ec4899", bug: "#84cc16",
    rock: "#b45309", ghost: "#7c3aed", dragon: "#6366f1", steel: "#64748b",
    dark: "#475569", fairy: "#f472b6", stellar: "#14b8a6"
  };

  const TYPE_CHART = {
    Normal: { Rock: 0.5, Ghost: 0.0, Steel: 0.5 },
    Fire: { Fire: 0.5, Water: 0.5, Grass: 2.0, Ice: 2.0, Bug: 2.0, Rock: 0.5, Dragon: 0.5, Steel: 2.0 },
    Water: { Fire: 2.0, Water: 0.5, Grass: 0.5, Ground: 2.0, Rock: 2.0, Dragon: 0.5 },
    Electric: { Water: 2.0, Electric: 0.5, Grass: 0.5, Ground: 0.0, Flying: 2.0, Dragon: 0.5 },
    Grass: { Fire: 0.5, Water: 2.0, Grass: 0.5, Poison: 0.5, Ground: 2.0, Flying: 0.5, Bug: 0.5, Rock: 2.0, Dragon: 0.5, Steel: 0.5 },
    Ice: { Fire: 0.5, Water: 0.5, Grass: 2.0, Ice: 0.5, Ground: 2.0, Flying: 2.0, Dragon: 2.0, Steel: 0.5 },
    Fighting: { Normal: 2.0, Ice: 2.0, Poison: 0.5, Flying: 0.5, Psychic: 0.5, Bug: 0.5, Rock: 2.0, Ghost: 0.0, Dark: 2.0, Steel: 2.0, Fairy: 0.5 },
    Poison: { Grass: 2.0, Poison: 0.5, Ground: 0.5, Rock: 0.5, Ghost: 0.5, Steel: 0.0, Fairy: 2.0 },
    Ground: { Fire: 2.0, Electric: 2.0, Grass: 0.5, Poison: 2.0, Flying: 0.0, Bug: 0.5, Rock: 2.0, Steel: 2.0 },
    Flying: { Electric: 0.5, Grass: 2.0, Fighting: 2.0, Bug: 2.0, Rock: 0.5, Steel: 0.5 },
    Psychic: { Fighting: 2.0, Poison: 2.0, Psychic: 0.5, Dark: 0.0, Steel: 0.5 },
    Bug: { Fire: 0.5, Grass: 2.0, Fighting: 0.5, Poison: 0.5, Flying: 0.5, Psychic: 2.0, Ghost: 0.5, Dark: 2.0, Steel: 0.5, Fairy: 0.5 },
    Rock: { Fire: 2.0, Ice: 2.0, Fighting: 0.5, Ground: 0.5, Flying: 2.0, Bug: 2.0, Steel: 0.5 },
    Ghost: { Normal: 0.0, Psychic: 2.0, Ghost: 2.0, Dark: 0.5 },
    Dragon: { Dragon: 2.0, Steel: 0.5, Fairy: 0.0 },
    Dark: { Fighting: 0.5, Psychic: 2.0, Ghost: 2.0, Dark: 0.5, Fairy: 0.5 },
    Steel: { Fire: 0.5, Water: 0.5, Electric: 0.5, Ice: 2.0, Rock: 2.0, Steel: 0.5, Fairy: 2.0 },
    Fairy: { Fire: 0.5, Fighting: 2.0, Poison: 0.5, Dragon: 2.0, Dark: 2.0, Steel: 0.5 }
  };
  const ALL_TYPES = Object.keys(TYPE_CHART);

  const STAT_ROWS = [{ k: "hp" }, { k: "atk" }, { k: "def" }, { k: "spa" }, { k: "spd" }, { k: "spe" }];
  const statName = (k) => (I18N.has("ss." + k) ? t("ss." + k) : I18N.has("bs." + k) ? t("bs." + k) : k);
  const statusLabel = (k) => (I18N.has("st." + k) ? t("st." + k) : k);
  const targetLabel = (k) => (I18N.has("tg." + k) ? t("tg." + k) : k);
  const flagLabel = (k) => (I18N.has("fl." + k) ? t("fl." + k) : k);

  const CATEGORY_BG = { Physical: "#ea580c", Special: "#0284c7", Status: "#64748b" };

  // Solo tiers oficiales y relevantes. Los "BL" juegan en el tier superior (donde realmente se usan) y los
  // valores entre paréntesis cuentan como su tier. Lo demás (Illegal, Unspecified, NFE, ZU) es "Sin tier".
  const OFFICIAL_TIERS = [
    { id: "Uber", label: "Ubers", members: ["Uber", "AG", "(Uber)"], icon: "bi-shield-shaded", color: "#dc2626" },
    { id: "OU", label: "OU", members: ["OU", "(OU)", "UUBL"], icon: "bi-trophy-fill", color: "#22c55e" },
    { id: "UU", label: "UU", members: ["UU", "RUBL"], icon: "bi-star-fill", color: "#eab308" },
    { id: "RU", label: "RU", members: ["RU", "NUBL"], icon: "bi-star-half", color: "#06b6d4" },
    { id: "NU", label: "NU", members: ["NU", "(NU)", "PUBL"], icon: "bi-star", color: "#3b82f6" },
    { id: "PU", label: "PU", members: ["PU", "(PU)", "ZUBL"], icon: "bi-circle-half", color: "#8b5cf6" },
    { id: "LC", label: "LC", members: ["LC"], icon: "bi-egg-fill", color: "#f472b6" },
  ];
  const tierGroupOf = (tr) => (OFFICIAL_TIERS.find((g) => g.members.includes(tr)) || { id: "none" }).id;
  const tierGroupLabel = (id) => (id === "none" ? t("tier.none") : (OFFICIAL_TIERS.find((g) => g.id === id) || {}).label || id);
  const TIER_ORDER = ["AG", "Uber", "(Uber)", "OU", "(OU)", "UUBL", "UU", "RUBL", "RU", "NUBL", "NU", "(NU)", "PUBL", "PU", "(PU)", "ZUBL", "ZU", "NFE", "LC", "Illegal", "Unspecified"];
  const tierLabel = (tr) => (I18N.has("tier." + tr) ? t("tier." + tr) : tr);
  const TIER_CLASS = {
    AG: "bg-danger", Uber: "bg-danger", "(Uber)": "bg-danger", OU: "bg-success", "(OU)": "bg-success",
    UUBL: "bg-warning text-dark", UU: "bg-warning text-dark", RUBL: "bg-info text-dark", RU: "bg-info text-dark",
    NUBL: "bg-primary", NU: "bg-primary", PUBL: "bg-secondary", PU: "bg-secondary", ZUBL: "bg-secondary", ZU: "bg-secondary"
  };

  const NOTABLE_FLAGS = ["contact", "sound", "punch", "bite", "bullet", "pulse", "slicing", "wind", "powder", "dance", "heal", "bypasssub", "reflectable", "snatch", "defrost", "charge", "recharge", "protect", "mirror", "distance", "gravity", "nonsky"];
  // Interacciones avanzadas (qué otros movimientos/efectos pueden o no copiarlo): solo en el desplegable
  const ADV_FLAGS = ["metronome", "nosleeptalk", "noassist", "failencore", "failcopycat", "failmimic", "failinstruct", "failmefirst", "nosketch", "cantusetwice", "futuremove", "noparentalbond", "pledgecombo", "mustpressure", "allyanim", "minimize"];
  const MOVE_FLAG_CHIPS = [
    ["contact", "bi-hand-index-thumb-fill", "#ef4444"], ["punch", "bi-hammer", "#f97316"], ["bite", "bi-emoji-angry-fill", "#dc2626"],
    ["slicing", "bi-scissors", "#38bdf8"], ["bullet", "bi-circle-fill", "#94a3b8"], ["sound", "bi-soundwave", "#a855f7"],
    ["wind", "bi-wind", "#67e8f9"], ["dance", "bi-music-note-beamed", "#f472b6"], ["pulse", "bi-broadcast-pin", "#ec4899"],
    ["powder", "bi-cloud-haze2-fill", "#a3e635"], ["heal", "bi-heart-pulse-fill", "#22c55e"], ["reflectable", "bi-arrow-repeat", "#fbbf24"],
    ["bypasssub", "bi-box-arrow-in-right", "#2dd4bf"], ["protect", "bi-shield-check", "#60a5fa"], ["mirror", "bi-copy", "#c084fc"],
    ["snatch", "bi-bag-fill", "#f59e0b"], ["distance", "bi-arrows-expand", "#38bdf8"], ["gravity", "bi-arrow-down-circle-fill", "#a1a1aa"],
    ["defrost", "bi-fire", "#fb923c"], ["charge", "bi-battery-charging", "#facc15"], ["recharge", "bi-hourglass-split", "#94a3b8"],
    ["nonsky", "bi-cloud-slash-fill", "#7dd3fc"],
  ];

  const ABILITY_CATS = {
    forme:    { color: "#a855f7", icon: "bi-shuffle" },
    weather:  { color: "#38bdf8", icon: "bi-cloud-sun-fill" },
    type:     { color: "#ec4899", icon: "bi-palette-fill" },
    entry:    { color: "#f59e0b", icon: "bi-box-arrow-in-right" },
    contact:  { color: "#ef4444", icon: "bi-hand-index-thumb-fill" },
    items:    { color: "#84cc16", icon: "bi-backpack2-fill" },
    status:   { color: "#2dd4bf", icon: "bi-capsule" },
    speed:    { color: "#facc15", icon: "bi-lightning-charge-fill" },
    defense:  { color: "#3b82f6", icon: "bi-shield-fill-check" },
    healing:  { color: "#4ade80", icon: "bi-heart-pulse-fill" },
    utility:  { color: "#94a3b8", icon: "bi-tools" },
    offense:  { color: "#f97316", icon: "bi-crosshair" },
    stats:    { color: "#818cf8", icon: "bi-graph-up-arrow" },
    passive:  { color: "#64748b", icon: "bi-circle-half" }
  };
  const ABILITY_CAT_ORDER = ["weather", "entry", "stats", "offense", "defense", "contact", "status", "speed", "healing", "type", "forme", "items", "utility", "passive"];
  const abCat = (id) => ABILITY_CATS[id] || ABILITY_CATS.passive;
  const abCatLabel = (id) => (I18N.has("abcat." + id) ? t("abcat." + id) : id);

  const ITEM_CAT_COLORS = {
    competitive: "#3b82f6", damage: "#ef4444",
    megastone: "#a855f7", zcrystal: "#f59e0b", berry: "#22c55e", choice: "#ef4444", plate: "#38bdf8",
    memory: "#94a3b8", drive: "#06b6d4", gem: "#ec4899", pokeball: "#f87171", mask: "#f97316",
    seed: "#84cc16", fossil: "#b7791f", mail: "#e2e8f0", herb: "#4ade80", orb: "#8b5cf6", general: "#64748b"
  };

  const itemCatColor = (cat) => ITEM_CAT_COLORS[String(cat || "").toLowerCase()] || "#64748b";

  /* Diccionarios de Traducción Reactiva Bilingües */
  const FALLBACK_PCAT = {
    mega: { es: "Megas", en: "Mega Evolutions" },
    primal: { es: "Primigenios", en: "Primal Reversions" },
    restricted: { es: "Legendarios", en: "Restricted Legendaries" },
    sublegend: { es: "Sub-Legend.", en: "Sub-Legendaries" },
    mythical: { es: "Míticos", en: "Mythical" },
    paradox: { es: "Paradoja", en: "Paradox" },
    ultrabeast: { es: "Ultra Entes", en: "Ultra Beasts" },
    base: { es: "Base", en: "Base Form" }
  };
  const pcatLabel = (id) => {
    if (I18N.has("pcat." + id)) return t("pcat." + id);
    if (I18N.has("tag." + id)) return t("tag." + id);
    const fb = FALLBACK_PCAT[id];
    return fb ? (fb[I18N.lang] || fb.en) : id;
  };

  const FALLBACK_ITEM_CATS = {
    competitive: { es: "Competitivos", en: "Competitive" },
    damage: { es: "Daño", en: "Damage" },
    berry: { es: "Bayas", en: "Berries" },
    choice: { es: "Elección", en: "Choice" },
    megastone: { es: "Megapiedras", en: "Mega Stones" },
    zcrystal: { es: "Cristales Z", en: "Z-Crystals" },
    orb: { es: "Orbes", en: "Orbs" },
    seed: { es: "Semillas", en: "Seeds" },
    herb: { es: "Hierbas", en: "Herbs" },
    general: { es: "Soporte/Bulk", en: "Support/Bulk" },
    plate: { es: "Tablas", en: "Plates" },
    memory: { es: "Discos", en: "Memories" },
    drive: { es: "Piro-módulos", en: "Drives" },
    gem: { es: "Gemas", en: "Gems" },
    pokeball: { es: "Poké Balls", en: "Poké Balls" },
    mask: { es: "Máscaras", en: "Masks" },
    fossil: { es: "Fósiles", en: "Fossils" },
    mail: { es: "Cartas", en: "Mail" }
  };
  const itemCatLabel = (id) => {
    if (I18N.has("ic." + id)) return t("ic." + id);
    const fb = FALLBACK_ITEM_CATS[id];
    return fb ? (fb[I18N.lang] || fb.en) : id;
  };

  const FALLBACK_MFLAG = {
    heal: { es: "Curación", en: "Healing" },
    contact: { es: "Contacto", en: "Contact" },
    sound: { es: "Sonido", en: "Sound" },
    slicing: { es: "Corte", en: "Slicing" },
    pulse: { es: "Pulsos", en: "Pulse" }
  };
  const moveFlagLabel = (id) => {
    if (I18N.has("fl." + id)) return t("fl." + id);
    const fb = FALLBACK_MFLAG[id];
    return fb ? (fb[I18N.lang] || fb.en) : id;
  };

  /* ------------------------------------------------------------------ */
  /* Utilidades Generales                                               */
  /* ------------------------------------------------------------------ */
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const normText = (s) => String(s ?? "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const compact = (s) => normText(s).replace(/[^a-z0-9]/g, "");
  const dash = (v, suffix = "") => (v === null || v === undefined || v === "" ? "—" : `${v}${suffix}`);
  const prettyKey = (k) => String(k).replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase());

  function typeName(tp) {
    const key = String(tp || "").toLowerCase();
    return I18N.has("type." + key) ? t("type." + key) : String(tp || "");
  }

  function typeColor(tp) {
    return TYPE_COLORS[String(tp || "").toLowerCase()] || "#64748b";
  }

  function typeBadge(tp) {
    if (!tp) return "";
    return `<span class="badge text-white px-2 py-1" style="background-color:${typeColor(tp)};font-size:0.65rem;font-weight:700;">${esc(typeName(tp).toUpperCase())}</span>`;
  }

  function categoryBadge(c) {
    const bg = CATEGORY_BG[c] || "#64748b";
    const label = I18N.has("cat." + c) ? t("cat." + c) : c || "";
    return `<span class="badge text-white px-2" style="background-color:${bg};font-size:0.65rem;">${esc(label.toUpperCase())}</span>`;
  }

  function tierBadge(tr, prefix = "") {
    if (!tr) return "";
    const cls = TIER_CLASS[tr] || "bg-dark border border-secondary text-secondary";
    return `<span class="badge ${cls}" style="font-size:0.65rem;">${esc(prefix)}${esc(tr)}</span>`;
  }

  function pastBadge() {
    return `<span class="badge bg-dark border border-warning text-warning" style="font-size:0.6rem;" title="${esc(t("c.past_title"))}">${t("c.past")}</span>`;
  }

  const spriteHtml = (p, size = 40) => Sprites.pokemon(p, size);
  const itemIconHtml = (it, size = 24) => Sprites.item(it, size);

  const KIND_OF_TAB = { pokemon: "pokemon", moves: "move", items: "item", abilities: "ability" };
  const dn = (kind, o) => L10N.name(kind, o);
  const nameOf = (kind, raw) => L10N.nameOf(kind, raw);
  const descTr = (kind, id) => L10N.desc(kind, id);
  const subName = (kind, o) => { const n = dn(kind, o); return n !== o.name ? o.name : ""; };
  const subLine = (kind, o) => {
    const s = subName(kind, o);
    return s ? `<div class="text-secondary text-truncate" style="font-size:0.62rem;">${esc(s)}</div>` : "";
  };

  function pickAbilityDesc(es, en, id) {
    const lang = I18N.lang;
    const tr = id ? descTr("ability", id) : "";
    let text = "", note = "", other = "", otherLang = "";
    if (lang === "en") {
      text = en || "";
      if (!text && es) { text = es; note = t("ab.fallback_es"); }
      else if (es && es !== text) { other = es; otherLang = "es"; }
    } else {
      text = tr || (lang === "es" ? es : "") || en || es || "";
      if (!tr) {
        if (lang === "es" && !es && en) note = t("ab.fallback_en");
        if (lang === "fr") note = en ? t("ab.fallback_en") : es ? t("ab.fallback_es") : "";
      }
      if (en && text !== en) { other = en; otherLang = "en"; }
    }
    return { text, other, otherLang, note };
  }

  function descBlock(trText, shortEn, longEn) {
    const parts = [];
    if (trText) parts.push(`<p class="text-light mb-2" style="font-size:0.88rem;line-height:1.5;">${esc(trText)}</p>`);
    if (shortEn) {
      parts.push(`<p class="${trText ? "text-secondary" : "text-light"} mb-2" style="font-size:${trText ? "0.76" : "0.85"}rem;">${trText ? `<b>${t("tech.en")}</b> ` : ""}${esc(shortEn)}</p>`);
    }
    if (longEn && !trText) parts.push(`<p class="text-light-emphasis mb-0" style="font-size:0.8rem;line-height:1.5;">${esc(longEn)}</p>`);
    return parts.join("") || `<p class="text-secondary fst-italic">${t("c.no_desc")}</p>`;
  }

  function calcStat(key, base, level, iv, ev, natureMult) {
    if (key === "hp") {
      if (base === 1) return 1;
      return Math.floor(((2 * base + iv + Math.floor(ev / 4)) * level) / 100) + level + 10;
    }
    return Math.floor((Math.floor(((2 * base + iv + Math.floor(ev / 4)) * level) / 100) + 5) * natureMult);
  }

  function lowKickPower(kg) {
    if (kg < 10) return 20;
    if (kg < 25) return 40;
    if (kg < 50) return 60;
    if (kg < 100) return 80;
    if (kg < 200) return 100;
    return 120;
  }

  function parseLearnCodes(codes) {
    const out = [];
    (codes || []).forEach((c) => {
      const m = /^(\d+)([A-Z])(\d*)$/.exec(c);
      if (m) out.push({ gen: parseInt(m[1], 10), method: m[2], level: m[3] ? parseInt(m[3], 10) : null, raw: c });
    });
    return out;
  }

  function learnMethodLabel(e) {
    if (e.method === "L") return e.level ? t("lm.Llv", { n: e.level }) : t("lm.L");
    return I18N.has("lm." + e.method) ? t("lm." + e.method) : e.method;
  }

  function learnSummary(codes, preferGen = 9) {
    const entries = parseLearnCodes(codes);
    if (!entries.length) return { html: "", gens: [], inPreferred: false, minLevel: null };
    const gens = [...new Set(entries.map((e) => e.gen))].sort((a, b) => b - a);
    const inPreferred = gens.includes(preferGen);
    const shownGen = inPreferred ? preferGen : gens[0];
    const shown = entries.filter((e) => e.gen === shownGen);
    const labels = [...new Set(shown.map(learnMethodLabel))];
    const chips = labels.map((l) => `<span class="badge bg-dark border border-secondary text-light-emphasis" style="font-size:0.62rem;">${esc(l)}</span>`).join(" ");
    const genNote = inPreferred ? "" : `<span class="badge bg-dark border border-warning text-warning" style="font-size:0.6rem;" title="${esc(t("lm.older_title"))}">${t("lm.older", { n: shownGen })}</span> `;
    const levels = shown.filter((e) => e.method === "L" && e.level !== null).map((e) => e.level);
    return { html: genNote + chips, gens, inPreferred, minLevel: levels.length ? Math.min(...levels) : null };
  }

  /* ------------------------------------------------------------------ */
  /* Listado y Controles                                                */
  /* ------------------------------------------------------------------ */
  const SORT_KEYS = {
    pokemon: ["num", "name", "bst", "hp", "atk", "def", "spa", "spd", "spe"],
    moves: ["name", "power", "accuracy", "pp", "priority", "learners"],
    items: ["name", "category"],
    abilities: ["name", "category", "count"]
  };

  function updateTabLabels() {
    tabButtons.forEach((btn) => {
      const cat = btn.getAttribute("data-cat");
      const icon = btn.querySelector("i") ? btn.querySelector("i").outerHTML : "";
      btn.innerHTML = `${icon} <span>${t("cp.tab_" + cat)}</span> <span class="badge bg-dark border border-secondary text-secondary ms-1">${(data[cat] || []).length}</span>`;
    });
  }

  async function initCompendium() {
    try {
      resultsCount.innerText = t("cp.loading");
      const res = await ApiService.getCompendium();
      data = {
        pokemon: res.pokemon || [],
        items: res.items || [],
        abilities: res.abilities || [],
        moves: res.moves || []
      };
      caps = res.capabilities || {};
      await L10N.load(I18N.lang);
      showCapabilityNotice();
      updateTabLabels();
      setupControls();
      refreshList();
    } catch (err) {
      resultsCount.innerHTML = `<span class="text-danger">${esc(t("common.error", { msg: err.message }))}</span>`;
      grid.innerHTML = `<div class="col-12 text-danger p-3">${t("cp.error_conn")}</div>`;
    }
  }

  function showCapabilityNotice() {
    if (!notice) return;
    const missing = [];
    if (!caps.learn_sources) missing.push(t("cp.miss_learn"));
    if (!caps.moves_full) missing.push(t("cp.miss_moves"));
    if (!caps.pokedex_extra) missing.push(t("cp.miss_extra"));
    if (!caps.long_descriptions) missing.push(t("cp.miss_desc"));
    if (!caps.items_extra) missing.push(t("cp.miss_icons"));
    if (I18N.lang !== "en" && !caps.translations) missing.push(t("cp.miss_i18n"));
    if (!missing.length) {
      notice.classList.add("d-none");
      return;
    }
    notice.innerHTML = `<i class="bi bi-info-circle me-1"></i> ${t("cp.notice", { list: esc(missing.join("; ")) })}`;
    notice.classList.remove("d-none");
  }

  function abilityMatches(a, catId) {
    return a.category === catId || (a.tags || []).includes(catId);
  }

  /* ------------------------------------------------------------------ */
  /* BARRA DE CHIPS MULTI-PESTAÑA CON CONTEOS DINÁMICOS EN VIVO          */
  /* ------------------------------------------------------------------ */
  function renderLegend() {
    const legend = document.getElementById("compendium-legend");
    if (!legend) return;

    let chipsConfig = [];

    if (currentTab === "pokemon") {
      const pList = data.pokemon || [];
      const cnt = (fn) => pList.filter(fn).length;
      chipsConfig = [
        ...OFFICIAL_TIERS.map((g) => ({ target: "filter2", val: "tier:" + g.id, label: g.label, icon: g.icon, color: g.color, count: cnt((p) => tierGroupOf(p.tier) === g.id) })),
        { target: "filter2", val: "tier:none", label: t("tier.none"), icon: "bi-question-circle-fill", color: "#64748b", count: cnt((p) => tierGroupOf(p.tier) === "none") },
        { target: "filter2", val: "cat:base", label: pcatLabel("base"), icon: "bi-circle", color: "#94a3b8", count: cnt((p) => p.forme === "Base") },
        { target: "filter2", val: "cat:mega", label: pcatLabel("mega"), icon: "bi-dna", color: "#a855f7", count: cnt((p) => p.is_mega) },
        { target: "filter2", val: "cat:primal", label: pcatLabel("primal"), icon: "bi-radioactive", color: "#ef4444", count: cnt((p) => p.is_primal) },
        { target: "filter2", val: "cat:mythical", label: pcatLabel("mythical"), icon: "bi-gem", color: "#fbbf24", count: cnt((p) => p.is_mythical) },
        { target: "filter2", val: "cat:sublegend", label: pcatLabel("sublegend"), icon: "bi-shield-check", color: "#818cf8", count: cnt((p) => p.is_sublegend) },
        { target: "filter2", val: "cat:restricted", label: pcatLabel("restricted"), icon: "bi-lightning-charge-fill", color: "#f97316", count: cnt((p) => p.is_restricted) },
        { target: "filter2", val: "cat:paradox", label: pcatLabel("paradox"), icon: "bi-hourglass-split", color: "#ec4899", count: cnt((p) => p.is_paradox) },
        { target: "filter2", val: "cat:ultrabeast", label: pcatLabel("ultrabeast"), icon: "bi-stars", color: "#14b8a6", count: cnt((p) => p.is_ultrabeast) },
      ];
    } else if (currentTab === "items") {
      const iList = data.items || [];
      const ICON = { competitive: "bi-shield-shaded", damage: "bi-crosshair", choice: "bi-slash-circle-fill", berry: "bi-egg-fill",
        orb: "bi-record-circle-fill", seed: "bi-tree-fill", herb: "bi-flower1", plate: "bi-layers-fill", memory: "bi-cpu-fill",
        drive: "bi-device-hdd-fill", gem: "bi-diamond-fill", pokeball: "bi-circle-half", mask: "bi-incognito", fossil: "bi-hexagon-fill",
        mail: "bi-envelope-fill", megastone: "bi-dna", zcrystal: "bi-gem", general: "bi-backpack2-fill" };
      chipsConfig = Object.keys(ICON).map((id) => ({
        target: "filter1", val: id, label: itemCatLabel(id), icon: ICON[id], color: itemCatColor(id),
        count: iList.filter((i) => i.category === id).length,
      }));
    } else if (currentTab === "moves") {
      const mList = data.moves || [];
      chipsConfig = [
        { target: "filter2", val: "cat:Physical", label: I18N.has("cat.Physical") ? t("cat.Physical") : "Físico", icon: "bi-bullseye", color: "#ea580c", count: mList.filter(m => m.category === "Physical").length },
        { target: "filter2", val: "cat:Special", label: I18N.has("cat.Special") ? t("cat.Special") : "Especial", icon: "bi-magic", color: "#0284c7", count: mList.filter(m => m.category === "Special").length },
        { target: "filter2", val: "cat:Status", label: I18N.has("cat.Status") ? t("cat.Status") : "Estado", icon: "bi-shield-shaded", color: "#64748b", count: mList.filter(m => m.category === "Status").length },
        { target: "filter2", val: "prio", label: I18N.has("f.priority") ? t("f.priority") : "Prioridad", icon: "bi-lightning-charge-fill", color: "#facc15", count: mList.filter(m => m.priority > 0).length },
        ...MOVE_FLAG_CHIPS.map(([id, icon, color]) => ({ target: "filter2", val: "flag:" + id, label: moveFlagLabel(id), icon, color,
          count: mList.filter((m) => (m.flags || []).includes(id)).length })),
      ];
    } else if (currentTab === "abilities") {
      const aList = data.abilities || [];
      chipsConfig = ABILITY_CAT_ORDER.map((id) => {
        const c = abCat(id);
        return {
          target: "filter1",
          val: id,
          label: abCatLabel(id),
          icon: c.icon,
          color: c.color,
          count: aList.filter((a) => abilityMatches(a, id)).length,
        };
      });
    }

    const availableChips = chipsConfig.filter((c) => c.count > 0);
    if (!availableChips.length) {
      legend.classList.add("d-none");
      legend.innerHTML = "";
      return;
    }

    legend.innerHTML = availableChips.map((c) => {
      const currentSelected = c.target === "filter2" ? filter2.value : filter1.value;
      const isActive = currentSelected === c.val;
      return `
        <button type="button" class="ab-legend-btn comp-chip-btn ${isActive ? "active" : ""}" 
                style="--ac:${c.color};" 
                data-target="${c.target}" 
                data-val="${esc(c.val)}">
          <i class="bi ${c.icon}"></i> ${esc(c.label)} 
          <span class="ab-legend-n">${c.count}</span>
        </button>`;
    }).join("");

    legend.classList.remove("d-none");
  }

  function setupControls() {
    const opt = (v, l) => `<option value="${esc(v)}">${esc(l)}</option>`;
    const show = (el, on) => el && el.classList.toggle("d-none", !on);
    const typeOptions = (label) => opt("", label) + ALL_TYPES.map((tp) => opt(tp, typeName(tp))).join("");

    filter1.innerHTML = opt("", t("f.all_types"));
    filter2.innerHTML = opt("", t("f.all_types"));

    if (currentTab === "pokemon") {
      filter1.innerHTML = typeOptions(t("f.all_types"));
      const tierIds = [...OFFICIAL_TIERS.map((g) => g.id), "none"];
      filter2.innerHTML = opt("", t("f.tier_cat")) +
        `<optgroup label="${esc(t("f.tier_group"))}">${tierIds.map((id) => opt("tier:" + id, tierGroupLabel(id))).join("")}</optgroup>` +
        `<optgroup label="${esc(t("f.cat_group"))}">` +
        ["base", "mega", "primal", "restricted", "sublegend", "mythical", "paradox", "ultrabeast"]
          .map((v) => opt("cat:" + v, pcatLabel(v))).join("") + `</optgroup>`;
      show(filter1, true); show(filter2, true);
    } else if (currentTab === "moves") {
      filter1.innerHTML = typeOptions(t("f.all_types"));
      const flagsPresent = new Set(data.moves.flatMap((m) => m.flags || []));
      const flagOpts = NOTABLE_FLAGS.filter((f) => flagsPresent.has(f)).map((f) => opt("flag:" + f, flagLabel(f))).join("");
      const advOpts = ADV_FLAGS.filter((f) => flagsPresent.has(f)).map((f) => opt("flag:" + f, flagLabel(f))).join("");
      filter2.innerHTML = opt("", t("f.move_cat_prop")) +
        `<optgroup label="${esc(t("f.cat_group"))}">${["Physical", "Special", "Status"].map((c) => opt("cat:" + c, t("cat." + c))).join("")}</optgroup>` +
        `<optgroup label="${esc(t("f.others"))}">${opt("prio", t("f.priority"))}${opt("gen9", t("f.available"))}${opt("past", t("f.past_only"))}</optgroup>` +
        (flagOpts ? `<optgroup label="${esc(t("f.property"))}">${flagOpts}</optgroup>` : "") +
        (advOpts ? `<optgroup label="${esc(t("f.property_adv"))}">${advOpts}</optgroup>` : "");
      show(filter1, true); show(filter2, true);
    } else if (currentTab === "items") {
      const cats = [...new Set(data.items.map((i) => i.category).filter(Boolean))].sort((a, b) => itemCatLabel(a).localeCompare(itemCatLabel(b)));
      filter1.innerHTML = opt("", t("f.all_cats")) + cats.map((c) => opt(c, itemCatLabel(c))).join("");
      filter2.innerHTML = opt("", t("f.availability")) + opt("gen9", t("f.available")) + opt("past", t("f.past_only")) + opt("nodesc", t("f.nodesc"));
      show(filter1, true); show(filter2, true);
    } else {
      filter1.innerHTML = opt("", t("f.all_cats")) + ABILITY_CAT_ORDER.map((c) => opt(c, abCatLabel(c))).join("");
      filter2.innerHTML = opt("", t("f.use")) + opt("used", t("f.used")) + opt("unused", t("f.unused")) + opt("nodata", t("ab.no_data"));
      show(filter1, true); show(filter2, true);
    }

    sortSel.innerHTML = SORT_KEYS[currentTab].map((v) => opt(v, t("sort." + v))).join("");
    renderLegend();
  }

  function applyFiltersAndSort() {
    const q = normText(searchInput.value.trim());
    const qc = compact(q);
    const f1 = filter1.value;
    const f2 = filter2.value;
    const list = data[currentTab] || [];

    let out = list.filter((item) => {
      if (q) {
        let hay;
        if (currentTab === "pokemon") hay = [item.name, dn("pokemon", item), ...(item.types || []), ...(item.types || []).map(typeName), ...(item.abilities || []), ...(item.abilities || []).map(a => nameOf("ability", a))].join(" ");
        else if (currentTab === "abilities") hay = [item.name, dn("ability", item), item.name_es, descTr("ability", item.id), item.desc_es, item.desc_en, abCatLabel(item.category), ...(item.tags || []).map(abCatLabel)].join(" ");
        else if (currentTab === "items") hay = [item.name, dn("item", item), item.desc, descTr("item", item.id), itemCatLabel(item.category)].join(" ");
        else hay = [item.name, dn("move", item), item.desc, descTr("move", item.id), item.category, typeName(item.type)].join(" ");
        const n = normText(hay);
        if (!n.includes(q) && !(qc && compact(hay).includes(qc))) return false;
      }
      if (currentTab === "pokemon") {
        if (f1 && !(item.types || []).includes(f1)) return false;
        if (f2.startsWith("tier:") && tierGroupOf(item.tier) !== f2.slice(5)) return false;
        if (f2.startsWith("cat:")) {
          const c = f2.slice(4);
          if (c === "mega" && !item.is_mega) return false;
          if (c === "primal" && !item.is_primal) return false;
          if (c === "restricted" && !item.is_restricted) return false;
          if (c === "sublegend" && !item.is_sublegend) return false;
          if (c === "mythical" && !item.is_mythical) return false;
          if (c === "paradox" && !item.is_paradox) return false;
          if (c === "ultrabeast" && !item.is_ultrabeast) return false;
          if (c === "base" && item.forme !== "Base") return false;
        }
      } else if (currentTab === "moves") {
        if (f1 && item.type !== f1) return false;
        if (f2.startsWith("cat:") && item.category !== f2.slice(4)) return false;
        if (f2 === "prio" && !item.priority) return false;
        if (f2 === "gen9" && item.is_past) return false;
        if (f2 === "past" && !item.is_past) return false;
        if (f2.startsWith("flag:") && !(item.flags || []).includes(f2.slice(5))) return false;
      } else if (currentTab === "items") {
        if (f1 && item.category !== f1) return false;
        if (f2 === "gen9" && item.is_past) return false;
        if (f2 === "past" && !item.is_past) return false;
        if (f2 === "nodesc" && item.has_desc) return false;
      } else {
        if (f1 && !abilityMatches(item, f1)) return false;
        if (f2 === "used" && !item.pokemon_count) return false;
        if (f2 === "unused" && item.pokemon_count) return false;
        if (f2 === "nodata" && !item.no_desc) return false;
      }
      return true;
    });

    const s = sortSel.value;
    const kindTab = KIND_OF_TAB[currentTab];
    const byName = (a, b) => dn(kindTab, a).localeCompare(dn(kindTab, b), I18N.lang);

    const relevance = q && sortSel.selectedIndex === 0
      ? (item) => { const rank = (nm) => { const n = normText(nm); return n === q ? 0 : n.startsWith(q) ? 1 : n.includes(q) ? 2 : 3; }; return Math.min(rank(item.name), rank(dn(kindTab, item))); }
      : null;
    const desc = (get) => (a, b) => (get(b) ?? -1) - (get(a) ?? -1) || byName(a, b);
    if (currentTab === "pokemon") {
      if (s === "num") out.sort((a, b) => a.num - b.num || byName(a, b));
      else if (s === "name") out.sort(byName);
      else if (s === "bst") out.sort(desc((p) => p.bst));
      else out.sort(desc((p) => (p.base_stats || {})[s]));
    } else if (currentTab === "moves") {
      if (s === "name") out.sort(byName);
      else if (s === "power") out.sort(desc((m) => m.base_power));
      else if (s === "accuracy") out.sort(desc((m) => m.accuracy ?? 101));
      else if (s === "pp") out.sort(desc((m) => m.pp));
      else if (s === "priority") out.sort(desc((m) => m.priority));
      else if (s === "learners") out.sort(desc((m) => m.learners_count));
    } else if (currentTab === "items") {
      if (s === "category") out.sort((a, b) => itemCatLabel(a.category).localeCompare(itemCatLabel(b.category)) || byName(a, b));
      else out.sort(byName);
    } else {
      if (s === "count") out.sort(desc((a) => a.pokemon_count));
      else if (s === "category") out.sort((a, b) => ABILITY_CAT_ORDER.indexOf(a.category) - ABILITY_CAT_ORDER.indexOf(b.category) || byName(a, b));
      else out.sort(byName);
    }
    if (relevance) out.sort((a, b) => relevance(a) - relevance(b));
    return out;
  }

  function refreshList(minRender = 0) {
    if (typeof minRender !== "number") minRender = 0;
    viewList = applyFiltersAndSort();
    resultsCount.innerText = t("cp.showing", { n: viewList.length, total: (data[currentTab] || []).length, what: t("cp.what_" + currentTab) });
    renderLegend();
    grid.innerHTML = "";
    renderedCount = 0;
    if (!viewList.length) {
      grid.innerHTML = `<div class="col-12 text-secondary text-center py-5 fst-italic">${t("cp.no_results")}</div>`;
      return;
    }
    renderMore();
    while (renderedCount < minRender && renderedCount < viewList.length) renderMore();
  }

  function renderMore() {
    if (renderedCount >= viewList.length) return;
    const slice = viewList.slice(renderedCount, renderedCount + PAGE_SIZE);
    const fn = { pokemon: pokemonCard, items: itemCard, abilities: abilityCard, moves: moveCard }[currentTab];
    grid.insertAdjacentHTML("beforeend", slice.map(fn).join(""));
    renderedCount += slice.length;
  }

  if ("IntersectionObserver" in window && sentinel) {
    new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) renderMore();
    }, { rootMargin: "600px" }).observe(sentinel);
  }

  /* --- Tarjetas del listado ------------------------------------------ */
  const COL = "col-12 col-sm-6 col-md-4 col-xl-3";

  function miniStats(stats) {
    const tip = STAT_ROWS.map((s) => statName(s.k)).join(" / ");
    return `<div class="dex-stats d-flex gap-1 mt-2 pt-2" title="${esc(tip)}">${STAT_ROWS.map((s) => {
      const v = (stats || {})[s.k] || 0;
      const h = Math.max(3, Math.round((v / 255) * 28));
      const color = v >= 100 ? "#22c55e" : v >= 70 ? "#eab308" : "#ef4444";
      return `<div class="flex-fill text-center" style="font-size:0.58rem;line-height:1.1;"><div class="d-flex align-items-end justify-content-center" style="height:28px;"><div style="width:100%;height:${h}px;background:${color};border-radius:3px;"></div></div><div class="text-secondary">${v}</div></div>`;
    }).join("")}</div>`;
  }

  function pokemonCard(p) {
    const special = [];
    if (p.is_mega) special.push(pcatLabel("mega"));
    if (p.is_primal) special.push(pcatLabel("primal"));
    if (p.is_restricted) special.push(pcatLabel("restricted"));
    if (p.is_paradox) special.push(pcatLabel("paradox"));
    if (p.is_mythical) special.push(pcatLabel("mythical"));
    if (p.is_sublegend) special.push(pcatLabel("sublegend"));
    if (p.is_ultrabeast) special.push(pcatLabel("ultrabeast"));
    
    const tags = special.map((tg) => `<span class="badge bg-dark border border-secondary text-info" style="font-size:0.58rem;">${esc(tg)}</span>`).join(" ");
    
    return `
      <div class="${COL}">
        <div class="card dex-card pk-ballmark p-3 h-100 compendium-card" style="--tc:${typeColor((p.types || [])[0])};" role="button" tabindex="0" data-open="pokemon:${esc(p.id)}">
          <div class="d-flex align-items-start justify-content-between gap-2">
            <div class="d-flex align-items-center gap-2 min-w-0">
              <span class="dex-plate">${spriteHtml(p, 56)}</span>
              <div class="min-w-0">
                <div class="dex-num">No.${String(p.num).padStart(3, "0")}</div>
                <h6 class="dex-name mb-0" style="word-break:break-word;line-height:1.1;" title="${esc(p.name)}">${esc(dn("pokemon", p))}</h6>${subLine("pokemon", p)}
                <div class="d-flex gap-1 mt-1 flex-wrap">${(p.types || []).map((tp) => typeBadge(tp)).join(" ")}</div>
              </div>
            </div>
            <div class="text-end flex-shrink-0">
              <span class="badge bg-primary-subtle text-primary border border-primary-subtle" style="font-size:0.62rem;">BST ${esc(p.bst || "—")}</span>
              <div class="mt-1">${tierBadge(p.tier)}</div>
            </div>
          </div>
          ${miniStats(p.base_stats)}
          <div class="text-secondary pt-2 mt-2" style="font-size:0.7rem;border-top:1px dashed rgba(255,255,255,0.14);">
            <b>${t("c.ab_short")}:</b> ${esc((p.abilities || []).map(a => nameOf("ability", a)).join(" • ") || "—")}
          </div>
          ${tags ? `<div class="d-flex flex-wrap gap-1 mt-2">${tags}</div>` : ""}
        </div>
      </div>`;
  }

  function moveCard(m) {
    return `
      <div class="${COL}">
        <div class="card mv-card pk-ballmark p-3 h-100 compendium-card" style="--tc:${typeColor(m.type)};" role="button" tabindex="0" data-open="move:${esc(m.id)}">
          <div class="d-flex align-items-center justify-content-between gap-2 mb-2">
            <div class="min-w-0"><span class="dex-name d-block" style="word-break:break-word;line-height:1.1;" title="${esc(m.name)}">${esc(dn("move", m))}</span>${subLine("move", m)}</div>
            ${typeBadge(m.type)}
          </div>
          <div class="d-flex align-items-center justify-content-between text-secondary mb-2 mv-stat">
            <span>${categoryBadge(m.category)} ${m.is_past ? pastBadge() : ""}</span>
            <span>${t("c.pot")} <b class="text-light">${dash(m.base_power)}</b> · ${t("c.prec")} <b class="text-light">${m.accuracy === null ? "—" : m.accuracy + "%"}</b>${m.pp ? ` · PP <b class="text-light">${m.pp}</b>` : ""}${m.priority ? ` · ${t("move.prio")} <b class="text-warning">${m.priority > 0 ? "+" : ""}${m.priority}</b>` : ""}</span>
          </div>
          <p class="text-secondary small mb-2 clamp-3" style="font-size:0.74rem;line-height:1.4;">${esc(descTr("move", m.id) || m.desc || t("c.no_desc"))}</p>
          <div class="mt-auto text-secondary" style="font-size:0.66rem;">${m.learners_count ? t("c.learners_n", { n: m.learners_count }) : t("c.learners_none")}</div>
        </div>
      </div>`;
  }

  function itemCard(i) {
    return `
      <div class="${COL}">
        <div class="card it-card pk-ballmark p-3 h-100 compendium-card" style="--tc:${itemCatColor(i.category)};" role="button" tabindex="0" data-open="item:${esc(i.id)}">
          <div class="d-flex align-items-center justify-content-between gap-2 mb-2">
            <div class="d-flex align-items-center gap-2 min-w-0">
              <span class="it-icon-plate">${itemIconHtml(i, 28)}</span>
              <div class="min-w-0"><h6 class="dex-name mb-0" style="word-break:break-word;line-height:1.1;" title="${esc(i.name)}">${esc(dn("item", i))}</h6>${subLine("item", i)}</div>
            </div>
            <span class="badge flex-shrink-0" style="font-size:0.62rem;background:${itemCatColor(i.category)};color:#0b1020;">${esc(itemCatLabel(i.category))}</span>
          </div>
          <p class="text-secondary small mb-0 clamp-4" style="font-size:0.74rem;line-height:1.4;">${(descTr("item", i.id) || i.desc) ? esc(descTr("item", i.id) || i.desc) : `<span class="fst-italic">${t("c.no_desc")}</span>`}</p>
          ${i.is_past ? `<div class="mt-2">${pastBadge()}</div>` : ""}
        </div>
      </div>`;
  }

  function abilityCard(a) {
    const c = abCat(a.category);
    const pick = pickAbilityDesc(a.desc_es, a.desc_en, a.id);
    const tagChips = (a.tags || []).map((id) => {
      const tc = abCat(id);
      return `<span class="ab-chip ab-chip-ghost" style="--ac:${tc.color};"><i class="bi ${tc.icon}"></i>${esc(abCatLabel(id))}</span>`;
    }).join(" ");
    return `
      <div class="${COL}">
        <div class="card ab-card p-3 h-100 compendium-card ${a.no_desc ? "ab-nodata" : ""}" style="--ac:${c.color};" role="button" tabindex="0" data-open="ability:${esc(a.id)}">
          <div class="d-flex align-items-start gap-2 mb-2">
            <span class="ab-icon"><i class="bi ${c.icon}"></i></span>
            <div class="min-w-0 flex-grow-1">
              <div class="ab-name" style="word-break:break-word;">${esc(dn("ability", a))}</div>
              ${subLine("ability", a)}
            </div>
          </div>
          <div class="d-flex flex-wrap gap-1 mb-2 align-items-center">
            <span class="ab-chip ab-chip-solid" style="--ac:${c.color};"><i class="bi ${c.icon}"></i>${esc(abCatLabel(a.category))}</span>
            ${tagChips}
            ${a.no_desc ? `<span class="ab-chip" style="--ac:#94a3b8;">${t("ab.no_data")}</span>` : ""}
            <span class="badge bg-dark border border-secondary text-secondary ms-auto" style="font-size:0.6rem;" title="${esc(t("ab.count"))}">${t("c.n_pokemon", { n: a.pokemon_count })}</span>
          </div>
          <p class="text-secondary small mb-0 clamp-4" style="font-size:0.74rem;line-height:1.4;">${pick.text ? esc(pick.text) : `<span class="fst-italic">${t("ab.no_data_long")}</span>`}</p>
        </div>
      </div>`;
  }

  /* ------------------------------------------------------------------ */
  /* Navegación y Detalle Modal                                         */
  /* ------------------------------------------------------------------ */
  async function openDetail(kind, id, { push = false } = {}) {
    if (!modal) return;
    if (!push) detailStack.length = 0;
    detailStack.push({ kind, id });
    updateBackBtn();
    modalHeader.innerHTML = `<div class="text-secondary small"><span class="spinner-border spinner-border-sm me-2"></span>${t("tb.loading")}</div>`;
    modalBody.innerHTML = "";
    if (!modalEl.classList.contains("show")) modal.show();

    try {
      const fetcher = { pokemon: "getPokemonDetail", move: "getMoveDetail", item: "getItemDetail", ability: "getAbilityDetail" }[kind];
      const d = await ApiService[fetcher](id);
      const top = detailStack[detailStack.length - 1];
      if (!top || top.kind !== kind || top.id !== id) return;
      currentDetail = { kind, d };
      learnersGen9 = true;
      RENDERERS[kind](d);
      modalBody.scrollTop = 0;
      if (modalEl.querySelector(".modal-body")) modalEl.querySelector(".modal-body").scrollTop = 0;
    } catch (err) {
      modalHeader.innerHTML = `<h6 class="mb-0 text-danger">${t("common.error", { msg: "" }).replace(/[: ]+$/, "")}</h6>`;
      modalBody.innerHTML = `<div class="text-danger">${esc(err.message)}</div>`;
    }
  }

  function updateBackBtn() {
    backBtn.classList.toggle("d-none", detailStack.length < 2);
  }

  backBtn.addEventListener("click", () => {
    if (detailStack.length < 2) return;
    detailStack.pop();
    const prev = detailStack.pop();
    openDetail(prev.kind, prev.id, { push: true });
  });

  modalEl.addEventListener("hidden.bs.modal", () => { detailStack.length = 0; currentDetail = null; updateBackBtn(); });

  function setModalColor(color) {
    const content = modalEl.querySelector(".modal-content");
    if (content) content.style.setProperty("--tc", color || "#64748b");
  }

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-open]");
    if (!el) return;
    if (!grid.contains(el) && !modalEl.contains(el)) return;
    const [kind, ...rest] = el.getAttribute("data-open").split(":");
    const id = rest.join(":");
    openDetail(kind, id, { push: modalEl.contains(el) });
  });

  document.addEventListener("keydown", (ev) => {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches && ev.target.matches(".compendium-card[data-open]")) {
      ev.preventDefault();
      ev.target.click();
    }
  });

  /* ------------------------------------------------------------------ */
  /* Piezas de ficha reutilizables                                       */
  /* ------------------------------------------------------------------ */
  const card = (title, icon, inner, extra = "") =>
    `<div class="card bg-body-tertiary border-secondary-subtle p-3 mb-3 ${extra}">${title ? `<h6 class="fw-bold text-info mb-2"><i class="bi ${icon} me-1"></i> ${title}</h6>` : ""}${inner}</div>`;

  const statBox = (label, value) =>
    `<div class="col-6 col-md-3"><div class="p-2 bg-dark rounded border border-secondary-subtle text-center h-100"><small class="text-secondary d-block" style="font-size:0.65rem;">${label}</small><strong class="text-light">${value}</strong></div></div>`;

  const infoRow = (label, valueHtml) =>
    `<div class="d-flex justify-content-between gap-3 border-bottom border-secondary-subtle py-1" style="font-size:0.78rem;"><span class="text-secondary">${label}</span><span class="text-light text-end">${valueHtml}</span></div>`;

  function pokeChip(p, extraHtml = "") {
    return `<button type="button" class="btn btn-sm btn-outline-secondary text-light-emphasis d-inline-flex align-items-center gap-1 py-0 px-2 poke-chip" data-open="pokemon:${esc(p.id)}" data-search="${esc(compact(p.name + " " + dn("pokemon", p)))}" style="font-size:0.72rem;">
      ${spriteHtml(p, 28)}<span>${esc(dn("pokemon", p))}</span>${extraHtml}</button>`;
  }

  function pokemonChipList(list, { withSearch = true, extraFn = null, id = "chips" } = {}) {
    if (!list.length) return `<div class="text-secondary fst-italic small">${t("chip.none")}</div>`;
    const search = withSearch && list.length > 12
      ? `<input type="text" class="form-control form-control-sm bg-dark text-light border-secondary mb-2 chip-filter" data-target="${id}" placeholder="${esc(t("chip.filter"))}" style="max-width:260px;">`
      : "";
    return `${search}<div id="${id}" class="d-flex flex-wrap gap-1" style="max-height:340px;overflow:auto;">${list.map((p) => pokeChip(p, extraFn ? extraFn(p) : "")).join("")}</div>`;
  }

  modalBody.addEventListener("input", (ev) => {
    const el = ev.target;
    if (el.classList.contains("chip-filter")) {
      const q = compact(el.value);
      document.querySelectorAll(`#${el.dataset.target} .poke-chip`).forEach((c) => {
        c.classList.toggle("d-none", q && !c.dataset.search.includes(q));
      });
    }
  });

  /* ------------------------------------------------------------------ */
  /* FICHA: POKÉMON                                                      */
  /* ------------------------------------------------------------------ */
  let pokeMoves = [];
  let pokeHasSources = false;
  const moveFilter = { search: "", type: "", cat: "", gen9: true, sort: "name" };

  function linkBtn(kind, id, label, extra = "") {
    return `<button type="button" class="btn btn-link p-0 text-info text-decoration-none" style="font-size:0.78rem;" data-open="${kind}:${esc(id)}">${extra}${esc(label)}</button>`;
  }

  function renderPokemon(d, keep = false) {
    pokeMoves = d.learnable_moves || [];
    pokeHasSources = !!d.has_learn_sources;
    if (!keep) {
      moveFilter.search = ""; moveFilter.type = ""; moveFilter.cat = ""; moveFilter.sort = "name";
      moveFilter.gen9 = pokeHasSources;
    }
    setModalColor(typeColor((d.types || [])[0]));

    const flagBadges = [];
    if (d.flags.is_mega) flagBadges.push(pcatLabel("mega"));
    if (d.flags.is_primal) flagBadges.push(pcatLabel("primal"));
    if (d.flags.is_restricted) flagBadges.push(pcatLabel("restricted"));
    if (d.flags.is_sublegend) flagBadges.push(pcatLabel("sublegend"));
    if (d.flags.is_mythical) flagBadges.push(pcatLabel("mythical"));
    if (d.flags.is_paradox) flagBadges.push(pcatLabel("paradox"));
    if (d.flags.is_ultrabeast) flagBadges.push(pcatLabel("ultrabeast"));

    modalHeader.innerHTML = `
      <span class="dex-plate" style="width:104px;height:104px;border-radius:20px;--tc:${typeColor((d.types || [])[0])};">${spriteHtml(d, 96)}</span>
      <div>
        <div class="dex-num">No.${String(d.num).padStart(3, "0")}</div>
        <h5 class="modal-title fw-bold text-light mb-0">${esc(dn("pokemon", d))}</h5>
        ${subName("pokemon", d) ? `<div class="text-secondary" style="font-size:0.72rem;">${esc(d.name)}</div>` : ""}
        <div class="d-flex flex-wrap align-items-center gap-1 mt-1">
          ${(d.types || []).map((tp) => typeBadge(tp)).join(" ")}
          ${tierBadge(d.tier)} ${d.doubles_tier && d.doubles_tier !== "Unspecified" ? tierBadge(d.doubles_tier, t("pk.doubles_prefix")) : ""}
          ${flagBadges.map((f) => `<span class="badge bg-dark border border-secondary text-info" style="font-size:0.62rem;">${esc(f)}</span>`).join(" ")}
        </div>
      </div>`;

    const statsTable = renderStatsTable(d);
    const abilities = renderPokemonAbilities(d);
    const defense = renderDefense(d.types || []);
    const profile = renderProfile(d);
    const evolution = renderEvolution(d);
    const forms = (d.forms || []).length ? card(t("pk.forms"), "bi-diagram-2", pokemonChipList(d.forms, { id: "forms-chips", withSearch: false })) : "";

    modalBody.innerHTML = `
      <ul class="nav nav-tabs border-secondary mb-3" role="tablist">
        <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#pk-tab-summary" type="button">${t("pk.tab_summary")}</button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#pk-tab-moves" type="button">${t("pk.tab_moves")} <span class="badge bg-dark border border-secondary text-secondary ms-1" id="pk-moves-tab-count">${pokeMoves.length}</span></button></li>
      </ul>
      <div class="tab-content">
        <div class="tab-pane fade show active" id="pk-tab-summary">
          <div class="row g-3">
            <div class="col-12 col-lg-6">${statsTable}${abilities}</div>
            <div class="col-12 col-lg-6">${profile}${defense}${evolution}${forms}</div>
          </div>
        </div>
        <div class="tab-pane fade" id="pk-tab-moves">${renderMovesPanel()}</div>
      </div>`;

    ["search", "type", "cat", "sort"].forEach((role) => {
      const el = modalBody.querySelector(`[data-mv="${role}"]`);
      if (el) el.value = moveFilter[role];
    });
    applyMoveFilters();
  }

  function renderStatsTable(d) {
    const s = d.base_stats || {};
    const rows = STAT_ROWS.map(({ k }) => {
      const v = s[k] || 0;
      const pct = Math.min(100, Math.round((v / 255) * 100));
      const color = v >= 120 ? "#22c55e" : v >= 90 ? "#84cc16" : v >= 70 ? "#eab308" : v >= 50 ? "#f97316" : "#ef4444";
      const min50 = calcStat(k, v, 50, 0, 0, 0.9), max50 = calcStat(k, v, 50, 31, 252, 1.1);
      const min100 = calcStat(k, v, 100, 0, 0, 0.9), max100 = calcStat(k, v, 100, 31, 252, 1.1);
      return `<tr>
        <td class="text-secondary fw-bold">${esc(statName(k))}</td>
        <td class="text-light fw-bold text-end">${v}</td>
        <td style="width:34%;"><div class="progress bg-dark" style="height:7px;"><div class="progress-bar" style="width:${pct}%;background:${color};"></div></div></td>
        <td class="text-secondary text-end">${min50}</td><td class="text-light text-end">${max50}</td>
        <td class="text-secondary text-end">${min100}</td><td class="text-light text-end">${max100}</td>
      </tr>`;
    }).join("");
    return card(t("pk.base_stats", { bst: esc(d.bst) }), "bi-bar-chart-fill", `
      <div class="table-responsive"><table class="table table-sm table-borderless mb-1 align-middle" style="font-size:0.78rem;--bs-table-bg:transparent;">
        <thead><tr class="text-secondary" style="font-size:0.65rem;"><th></th><th class="text-end">${t("pk.col_base")}</th><th></th><th class="text-end" colspan="2">${t("pk.col_lv50")}</th><th class="text-end" colspan="2">${t("pk.col_lv100")}</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <div class="text-secondary" style="font-size:0.65rem;">${t("pk.stat_note")}</div>`);
  }

  function renderPokemonAbilities(d) {
    const items = (d.ability_details || []).map((a) => {
      const c = abCat(a.category);
      const pick = pickAbilityDesc(a.desc_es, a.desc_en, a.id);
      const slotLabel = I18N.has("slot." + a.slot) ? t("slot." + a.slot) : a.slot_label;
      return `
      <div class="ab-card p-2 mb-2" style="--ac:${c.color};border-radius:12px;">
        <div class="d-flex align-items-center justify-content-between gap-2">
          <div class="d-flex align-items-center gap-2 min-w-0">
            <span class="ab-icon" style="width:30px;height:30px;border-radius:10px;font-size:0.9rem;"><i class="bi ${c.icon}"></i></span>
            <button type="button" class="btn btn-link p-0 ab-name text-decoration-none text-truncate" style="color:#fff;" data-open="ability:${esc(a.id)}">${esc(dn("ability", a))}${subName("ability", a) ? ` <span class="text-secondary fw-normal">· ${esc(a.name)}</span>` : ""}</button>
          </div>
          <span class="badge ${a.hidden ? "bg-warning text-dark" : "bg-secondary"} flex-shrink-0" style="font-size:0.6rem;">${esc(slotLabel)}</span>
        </div>
        <div class="d-flex flex-wrap gap-1 mt-1"><span class="ab-chip" style="--ac:${c.color};"><i class="bi ${c.icon}"></i>${esc(abCatLabel(a.category))}</span></div>
        <div class="text-light-emphasis mt-1" style="font-size:0.78rem;line-height:1.45;">${pick.text ? esc(pick.text) : `<span class="fst-italic text-secondary">${t("ab.no_data_long")}</span>`}</div>
      </div>`;
    }).join("");
    return card(t("pk.abilities"), "bi-stars", items || `<div class="text-secondary fst-italic small">${t("chip.none")}</div>`);
  }

  function renderProfile(d) {
    const x = d.extra || {};
    const rows = [];
    const pct = (v) => (v * 100).toFixed(1).replace(/\.0$/, "");
    rows.push(infoRow(t("pk.base_species"), esc(d.base_species)));
    if (d.forme && d.forme !== "Base") rows.push(infoRow(t("pk.forme"), esc(d.forme)));
    if (x.heightm !== undefined) rows.push(infoRow(t("pk.height"), `${x.heightm} m`));
    if (x.weightkg !== undefined) {
      rows.push(infoRow(t("pk.weight"), `${x.weightkg} kg`));
      rows.push(infoRow(t("pk.lowkick"), `<b>${lowKickPower(x.weightkg)}</b>`));
    }
    if (x.eggGroups) rows.push(infoRow(t("pk.egg"), esc(x.eggGroups.join(", "))));
    if (x.gender) rows.push(infoRow(t("pk.gender"), x.gender === "N" ? t("pk.gender_n") : x.gender === "M" ? t("pk.gender_m") : t("pk.gender_f")));
    else if (x.genderRatio) rows.push(infoRow(t("pk.gender_ratio"), `${pct(x.genderRatio.M)}% ♂ / ${pct(x.genderRatio.F)}% ♀`));
    if (x.color) rows.push(infoRow(t("pk.color"), esc(x.color)));
    if (x.gen) rows.push(infoRow(t("pk.gen"), esc(x.gen)));
    if (d.required_item) rows.push(infoRow(t("pk.req_item"), linkBtn("item", d.required_item, nameOf("item", d.required_item), `<span class="me-1">${itemIconHtml(d.required_item, 20)}</span>`)));
    if (x.requiredItems && !d.required_item) rows.push(infoRow(t("pk.req_items"), esc(x.requiredItems.join(", "))));
    if (x.requiredMove) rows.push(infoRow(t("pk.req_move"), linkBtn("move", x.requiredMove, nameOf("move", x.requiredMove))));
    if (x.requiredAbility) rows.push(infoRow(t("pk.req_ability"), esc(x.requiredAbility)));
    if (x.battleOnly) rows.push(infoRow(t("pk.battle_only"), esc([].concat(x.battleOnly).join(", "))));
    if (x.changesFrom) rows.push(infoRow(t("pk.changes_from"), esc(x.changesFrom)));
    if (x.canGigantamax) rows.push(infoRow(t("pk.gmax"), esc(x.canGigantamax)));
    if (x.tags && x.tags.length) rows.push(infoRow(t("pk.tags"), esc(x.tags.join(", "))));
    rows.push(infoRow(t("pk.tier_singles"), tierBadge(d.tier)));
    rows.push(infoRow(t("pk.tier_doubles"), tierBadge(d.doubles_tier)));
    rows.push(infoRow(t("pk.tier_natdex"), tierBadge(d.natdex_tier)));
    return card(t("pk.profile"), "bi-info-circle-fill", rows.join(""));
  }

  function evoHow(how) {
    if (!how) return "";
    const parts = [];
    if (how.evoType === "useItem") parts.push(how.evoItem ? t("evo.use", { item: how.evoItem }) : t("evo.use_generic"));
    else if (how.evoType === "trade") parts.push(how.evoItem ? t("evo.trade_item", { item: how.evoItem }) : t("evo.trade"));
    else if (how.evoType === "levelFriendship") parts.push(t("evo.friendship"));
    else if (how.evoType === "levelHold") parts.push(t("evo.level_hold", { item: how.evoItem || "?" }));
    else if (how.evoType === "levelMove") parts.push(t("evo.level_move", { move: how.evoMove || "?" }));
    else if (how.evoType === "levelExtra" || how.evoType === "other") parts.push(t("evo.special"));
    if (how.evoLevel) parts.push(t("evo.level", { n: how.evoLevel }));
    if (how.evoCondition) parts.push(how.evoCondition);
    if (!parts.length && how.evoItem) parts.push(how.evoItem);
    return parts.join(" · ");
  }

  function renderEvoNode(n, currentId) {
    const how = evoHow(n.how);
    const me = n.id === currentId;
    const kids = (n.children || []).map((c) => renderEvoNode(c, currentId)).join("");
    return `<div class="d-flex align-items-center gap-2 mb-1 flex-wrap">
      ${how ? `<span class="text-secondary" style="font-size:0.65rem;"><i class="bi bi-arrow-right"></i> ${esc(how)}</span>` : ""}
      <button type="button" class="btn btn-sm ${me ? "btn-info" : "btn-outline-secondary text-light-emphasis"} d-inline-flex align-items-center gap-1 py-0 px-2" data-open="pokemon:${esc(n.id)}" style="font-size:0.72rem;">${spriteHtml(n, 34)}<span>${esc(dn("pokemon", n))}</span></button>
      ${kids ? `<div class="d-flex flex-column ms-1">${kids}</div>` : ""}
    </div>`;
  }

  function renderEvolution(d) {
    if (!d.evolution) return "";
    return card(t("pk.evolution"), "bi-arrow-up-right-circle", renderEvoNode(d.evolution, d.id));
  }

  function renderDefense(types) {
    const groups = new Map([[4, []], [2, []], [1, []], [0.5, []], [0.25, []], [0, []]]);
    ALL_TYPES.forEach((atk) => {
      let mult = 1;
      types.forEach((def) => { mult *= TYPE_CHART[atk][def] !== undefined ? TYPE_CHART[atk][def] : 1; });
      if (groups.has(mult)) groups.get(mult).push(atk);
    });
    const ROWS = [
      { m: 4, cls: "m-x4", sym: "×4", key: "match.x4" },
      { m: 2, cls: "m-x2", sym: "×2", key: "match.x2" },
      { m: 1, cls: "m-x1", sym: "×1", key: "match.x1" },
      { m: 0.5, cls: "m-x05", sym: "½", key: "match.x05" },
      { m: 0.25, cls: "m-x025", sym: "¼", key: "match.x025" },
      { m: 0, cls: "m-x0", sym: "0", key: "match.x0" },
    ];
    const chip = (tp) => `<span class="def-chip" style="background:${typeColor(tp)};">${esc(typeName(tp).toUpperCase())}</span>`;
    const rows = ROWS.map((r) => {
      const list = groups.get(r.m);
      return `<div class="def-row">
        <div class="def-label"><span class="def-mult ${r.cls}">${r.sym}</span><span class="def-label-text">${esc(t(r.key))}</span></div>
        <div class="def-chips">${list.length ? list.map(chip).join("") : `<span class="def-none">${t("common.none")}</span>`}</div>
      </div>`;
    }).join("");
    return card(t("pk.defense"), "bi-shield-shaded", `<div class="def-table">${rows}</div>
      <div class="text-secondary mt-2" style="font-size:0.65rem;">${t("pk.defense_note")}</div>`);
  }

  /* --- Panel de movimientos del Pokémon ------------------------------- */
  function renderMovesPanel() {
    const typeOpts = ALL_TYPES.map((tp) => `<option value="${tp}">${esc(typeName(tp))}</option>`).join("");
    return card("", "", `
      <div class="row g-2 mb-2 align-items-center">
        <div class="col-12 col-md-4"><input type="text" class="form-control form-control-sm bg-dark text-light border-secondary" data-mv="search" placeholder="${esc(t("mv.search_ph"))}"></div>
        <div class="col-6 col-md-2"><select class="form-select form-select-sm bg-dark text-light border-secondary" data-mv="type"><option value="">${t("mv.type")}</option>${typeOpts}</select></div>
        <div class="col-6 col-md-2"><select class="form-select form-select-sm bg-dark text-light border-secondary" data-mv="cat"><option value="">${t("mv.cat")}</option><option value="Physical">${t("cat.Physical")}</option><option value="Special">${t("cat.Special")}</option><option value="Status">${t("cat.Status")}</option></select></div>
        <div class="col-6 col-md-2"><select class="form-select form-select-sm bg-dark text-light border-secondary" data-mv="sort">
          <option value="name">${t("mv.sort_name")}</option><option value="power">${t("mv.sort_power")}</option><option value="accuracy">${t("mv.sort_acc")}</option><option value="pp">${t("mv.sort_pp")}</option><option value="type">${t("mv.sort_type")}</option>${pokeHasSources ? `<option value="level">${t("mv.sort_level")}</option>` : ""}</select></div>
        <div class="col-6 col-md-2"><div class="form-check form-switch small mb-0 ${pokeHasSources ? "" : "d-none"}"><input class="form-check-input" type="checkbox" role="switch" id="mv-gen9" data-mv="gen9" ${moveFilter.gen9 ? "checked" : ""}><label class="form-check-label text-secondary" for="mv-gen9">${t("mv.gen9")}</label></div></div>
      </div>
      <div class="text-secondary small mb-2" id="pk-moves-counter"></div>
      ${pokeHasSources ? "" : `<div class="text-secondary small fst-italic mb-2">${t("mv.need_script")}</div>`}
      <div class="table-responsive" style="max-height:520px;overflow:auto;">
        <table class="table table-sm table-dark table-hover align-middle mb-0" style="font-size:0.76rem;">
          <thead class="sticky-top" style="top:0;z-index:1;"><tr class="text-secondary" style="font-size:0.65rem;"><th>${t("mv.th_move")}</th><th>${t("mv.th_cat")}</th><th class="text-end">${t("mv.th_pow")}</th><th class="text-end">${t("mv.th_acc")}</th><th class="text-end">PP</th><th>${t("mv.th_learn")}</th><th>${t("mv.th_effect")}</th></tr></thead>
          <tbody id="pk-moves-body"></tbody>
        </table>
      </div>`);
  }

  function applyMoveFilters() {
    const body = document.getElementById("pk-moves-body");
    if (!body) return;
    const q = normText(moveFilter.search);

    let rows = pokeMoves.map((m) => ({ m, learn: learnSummary(m.sources) }));
    rows = rows.filter(({ m, learn }) => {
      if (q && !normText(m.name + " " + dn("move", m) + " " + (descTr("move", m.id) || m.short_desc || "")).includes(q)) return false;
      if (moveFilter.type && m.type !== moveFilter.type) return false;
      if (moveFilter.cat && m.category !== moveFilter.cat) return false;
      if (pokeHasSources && moveFilter.gen9 && !learn.inPreferred) return false;
      return true;
    });

    const s = moveFilter.sort;
    const byName = (a, b) => dn("move", a.m).localeCompare(dn("move", b.m), I18N.lang);
    if (s === "power") rows.sort((a, b) => (b.m.base_power ?? -1) - (a.m.base_power ?? -1) || byName(a, b));
    else if (s === "accuracy") rows.sort((a, b) => (b.m.accuracy ?? 101) - (a.m.accuracy ?? 101) || byName(a, b));
    else if (s === "pp") rows.sort((a, b) => (b.m.pp ?? -1) - (a.m.pp ?? -1) || byName(a, b));
    else if (s === "type") rows.sort((a, b) => a.m.type.localeCompare(b.m.type) || byName(a, b));
    else if (s === "level") rows.sort((a, b) => (a.learn.minLevel ?? 999) - (b.learn.minLevel ?? 999) || byName(a, b));
    else rows.sort(byName);

    const counter = document.getElementById("pk-moves-counter");
    if (counter) counter.innerText = t("mv.count", { n: rows.length, total: pokeMoves.length });

    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="7" class="text-center text-secondary fst-italic py-4">${t("mv.none")}</td></tr>`;
      return;
    }
    body.innerHTML = rows.map(({ m, learn }) => `
      <tr role="button" data-open="move:${esc(m.id)}">
        <td class="text-nowrap"><span class="fw-bold text-light">${esc(dn("move", m))}${subName("move", m) ? ` <small class="text-secondary">(${esc(m.name)})</small>` : ""}</span> ${typeBadge(m.type)} ${m.is_past ? pastBadge() : ""}</td>
        <td>${categoryBadge(m.category)}</td>
        <td class="text-end text-light">${dash(m.base_power)}</td>
        <td class="text-end text-light">${m.accuracy === null ? "—" : m.accuracy + "%"}</td>
        <td class="text-end text-light">${dash(m.pp)}</td>
        <td>${learn.html || '<span class="text-secondary">—</span>'}${m.via ? ` <span class="badge bg-dark border border-info text-info" style="font-size:0.58rem;" title="${esc(t("mv.via_title"))}">${esc(t("mv.via", { name: m.via }))}</span>` : ""}</td>
        <td class="text-secondary" style="min-width:220px;">${esc(descTr("move", m.id) || m.short_desc || "")}</td>
      </tr>`).join("");
  }

  modalBody.addEventListener("input", (ev) => {
    const role = ev.target.dataset && ev.target.dataset.mv;
    if (role === "search") { moveFilter.search = ev.target.value; applyMoveFilters(); }
  });
  modalBody.addEventListener("change", (ev) => {
    const role = ev.target.dataset && ev.target.dataset.mv;
    if (!role || role === "search") return;
    if (role === "gen9") moveFilter.gen9 = ev.target.checked;
    else moveFilter[role] = ev.target.value;
    applyMoveFilters();
  });

  /* ------------------------------------------------------------------ */
  /* FICHA: MOVIMIENTO                                                   */
  /* ------------------------------------------------------------------ */
  function describeBoosts(b) {
    return Object.entries(b || {}).map(([k, v]) => `${statName(k)} ${v > 0 ? "+" : "−"}${Math.abs(v)}`).join(", ");
  }

  function describeSecondary(sec) {
    const bits = [];
    if (sec.boosts) bits.push(t("mp.sec_target", { x: describeBoosts(sec.boosts) }));
    if (sec.self && sec.self.boosts) bits.push(t("mp.sec_self", { x: describeBoosts(sec.self.boosts) }));
    if (sec.status) bits.push(t("mp.sec_status", { x: statusLabel(sec.status) }));
    if (sec.volatileStatus) bits.push(t("mp.sec_volatile", { x: sec.volatileStatus }));
    if (sec.onHit && !bits.length) bits.push(t("mp.sec_onhit"));
    if (!bits.length) bits.push(esc(JSON.stringify(sec)));
    return `${sec.chance ? t("mp.chance", { n: sec.chance }) : ""}${bits.join("; ")}`;
  }

  function moveProperties(d) {
    const p = d.properties || {};
    const rows = [];
    const frac = (v) => (Array.isArray(v) ? `${v[0]}/${v[1]}` : v);
    if (p.drain) rows.push([t("mp.drain"), t("mp.drain_v", { x: frac(p.drain) })]);
    if (p.recoil) rows.push([t("mp.recoil"), t("mp.recoil_v", { x: frac(p.recoil) })]);
    if (p.mindBlownRecoil) rows.push([t("mp.recoil"), t("mp.recoil_half")]);
    if (p.struggleRecoil) rows.push([t("mp.recoil"), t("mp.recoil_quarter")]);
    if (p.hasCrashDamage) rows.push([t("mp.crash"), t("mp.crash_v")]);
    if (p.heal) rows.push([t("mp.heal"), t("mp.heal_v", { x: frac(p.heal) })]);
    if (p.multihit) rows.push([t("mp.multihit"), Array.isArray(p.multihit) ? t("mp.multihit_range", { a: p.multihit[0], b: p.multihit[1] }) : t("mp.multihit_n", { n: p.multihit })]);
    if (p.critRatio && p.critRatio !== 1) rows.push([t("mp.crit"), t("mp.crit_v", { n: p.critRatio - 1 })]);
    if (p.willCrit) rows.push([t("mp.willcrit"), t("mp.willcrit_v")]);
    if (p.ohko) rows.push([t("mp.ohko"), t("mp.ohko_v")]);
    if (p.damage) rows.push([t("mp.damage"), p.damage === "level" ? t("mp.damage_level") : t("mp.damage_hp", { n: p.damage })]);
    if (p.selfSwitch) rows.push([t("mp.switch"), t("mp.switch_v") + (p.selfSwitch === "copyvolatile" ? " " + t("mp.switch_copy") : "")]);
    if (p.forceSwitch) rows.push([t("mp.force"), t("mp.force_v")]);
    if (p.boosts) rows.push([t("mp.boosts_t"), describeBoosts(p.boosts)]);
    if (p.self && p.self.boosts) rows.push([t("mp.boosts_s"), describeBoosts(p.self.boosts)]);
    if (p.self && p.self.volatileStatus) rows.push([t("mp.self_vol"), esc(p.self.volatileStatus)]);
    if (p.status) rows.push([t("mp.status"), statusLabel(p.status)]);
    if (p.volatileStatus) rows.push([t("mp.volatile"), esc(p.volatileStatus)]);
    if (p.sideCondition) rows.push([t("mp.side"), esc(p.sideCondition)]);
    if (p.slotCondition) rows.push([t("mp.slot"), esc(p.slotCondition)]);
    if (p.weather) rows.push([t("mp.weather"), esc(p.weather)]);
    if (p.terrain) rows.push([t("mp.terrain"), esc(p.terrain)]);
    if (p.pseudoWeather) rows.push([t("mp.pseudo"), esc(p.pseudoWeather)]);
    if (p.secondary) rows.push([t("mp.secondary"), describeSecondary(p.secondary)]);
    if (p.secondaries) rows.push([t("mp.secondaries"), p.secondaries.map(describeSecondary).join("<br>")]);
    if (p.overrideOffensiveStat) rows.push([t("mp.off_stat"), statName(p.overrideOffensiveStat)]);
    if (p.overrideDefensiveStat) rows.push([t("mp.def_stat"), statName(p.overrideDefensiveStat)]);
    if (p.overrideOffensivePokemon) rows.push([t("mp.off_poke"), p.overrideOffensivePokemon === "target" ? t("mp.off_target") : p.overrideOffensivePokemon]);
    if (p.ignoreDefensive) rows.push([t("mp.ign_def"), t("mp.ign_def_v")]);
    if (p.ignoreEvasion) rows.push([t("mp.ign_eva"), t("mp.ign_eva_v")]);
    if (p.ignoreImmunity) rows.push([t("mp.ign_imm"), t("mp.ign_imm_v")]);
    if (p.ignoreAbility) rows.push([t("mp.ign_ab"), t("mp.ign_ab_v")]);
    if (p.breaksProtect) rows.push([t("mp.breaks"), t("mp.breaks_v")]);
    if (p.stallingMove) rows.push([t("mp.stalling"), t("mp.stalling_v")]);
    if (p.thawsTarget) rows.push([t("mp.thaws"), t("mp.thaws_v")]);
    if (p.sleepUsable) rows.push([t("mp.sleep"), t("mp.sleep_v")]);
    if (p.isFutureMove) rows.push([t("mp.future"), t("mp.future_v")]);
    if (p.noPPBoosts) rows.push([t("mp.nopp"), t("mp.nopp_v")]);
    if (p.zMove) rows.push([t("mp.zmove"), p.zMove.basePower ? t("mp.power_n", { n: p.zMove.basePower }) : p.zMove.effect ? esc(p.zMove.effect) : p.zMove.boost ? describeBoosts(p.zMove.boost) : esc(JSON.stringify(p.zMove))]);
    if (p.maxMove) rows.push([t("mp.maxmove"), p.maxMove.basePower ? t("mp.power_n", { n: p.maxMove.basePower }) : esc(JSON.stringify(p.maxMove))]);
    if (p.contestType) rows.push([t("mp.contest"), esc(p.contestType)]);
    if (p.isZ) rows.push([t("mp.class"), t("mp.isz_v")]);
    if (p.isMax) rows.push([t("mp.class"), t("mp.ismax_v")]);

    const known = new Set(["drain", "recoil", "mindBlownRecoil", "struggleRecoil", "hasCrashDamage", "heal", "multihit", "critRatio", "willCrit", "ohko", "damage", "selfSwitch", "forceSwitch", "boosts", "self", "status", "volatileStatus", "sideCondition", "slotCondition", "weather", "terrain", "pseudoWeather", "secondary", "secondaries", "overrideOffensiveStat", "overrideDefensiveStat", "overrideOffensivePokemon", "ignoreDefensive", "ignoreEvasion", "ignoreImmunity", "ignoreAbility", "breaksProtect", "stallingMove", "thawsTarget", "sleepUsable", "isFutureMove", "noPPBoosts", "zMove", "maxMove", "contestType", "isZ", "isMax"]);
    Object.keys(p).filter((k) => !known.has(k)).forEach((k) => rows.push([prettyKey(k), esc(typeof p[k] === "object" ? JSON.stringify(p[k]) : p[k])]));
    return rows;
  }

  function renderMove(d) {
    setModalColor(typeColor(d.type));
    modalHeader.innerHTML = `
      <span class="dex-plate" style="width:56px;height:56px;border-radius:16px;--tc:${typeColor(d.type)};"><i class="bi bi-lightning-charge-fill text-warning fs-3"></i></span>
      <div>
        <h5 class="modal-title fw-bold text-light mb-0">${esc(dn("move", d))}${d.num ? ` <span class="dex-num ms-1">No.${esc(d.num)}</span>` : ""}</h5>
        ${subName("move", d) ? `<div class="text-secondary" style="font-size:0.72rem;">${esc(d.name)}</div>` : ""}
        <div class="d-flex flex-wrap gap-1 mt-1">${typeBadge(d.type)} ${categoryBadge(d.category)} ${d.is_past ? pastBadge() : ""}</div>
      </div>`;

    const accText = d.accuracy === null ? (d.never_misses ? t("mvs.never_miss") : "—") : d.accuracy + "%";
    const prio = d.priority ? (d.priority > 0 ? "+" : "") + d.priority : "0";

    const flagList = d.flags || [];
    const notable = flagList.filter((f) => NOTABLE_FLAGS.includes(f));
    const technical = flagList.filter((f) => !NOTABLE_FLAGS.includes(f));
    const flagChip = (f, muted) => `<span class="badge ${muted ? "bg-dark border border-secondary text-secondary" : "bg-secondary-subtle text-light"}" style="font-size:0.66rem;" title="${esc(f)}">${esc(flagLabel(f))}</span>`;

    const propRows = moveProperties(d);
    const learners = d.learners || [];
    const hasLearnSources = learners.some((l) => l.sources && l.sources.length);
    const gen9Count = hasLearnSources ? learners.filter((l) => learnSummary(l.sources).inPreferred).length : null;

    modalBody.innerHTML = `
      <div class="row g-2 mb-3">
        ${statBox(t("mvs.power"), dash(d.base_power))}
        ${statBox(t("mvs.accuracy"), accText)}
        ${statBox(t("mvs.pp"), dash(d.pp))}
        ${statBox(t("mvs.priority"), prio)}
      </div>
      <div class="row g-3">
        <div class="col-12 col-lg-6">
          ${card(t("mvs.effect"), "bi-info-circle-fill", descBlock(descTr("move", d.id), d.short_desc, d.desc))}
          ${card(t("mvs.data"), "bi-sliders", `
            ${infoRow(t("mvs.target"), d.target ? esc(targetLabel(d.target)) : `<span class="text-secondary">${t("mvs.target_need")}</span>`)}
            ${infoRow(t("mvs.type"), typeBadge(d.type))}
            ${infoRow(t("mvs.category"), categoryBadge(d.category))}
            ${infoRow(t("mvs.avail"), d.is_past ? t("mvs.avail_no") : t("mvs.avail_yes"))}
            ${learners.length ? infoRow(t("mvs.learners"), learners.length + (gen9Count !== null ? " " + t("mvs.learners_gen9", { n: gen9Count }) : "")) : ""}`)}
          ${flagList.length ? card(t("mvs.flags"), "bi-flag-fill", `
            <div class="d-flex flex-wrap gap-1 mb-2">${notable.map((f) => flagChip(f, false)).join("") || `<span class="text-secondary small fst-italic">${t("mvs.no_notable")}</span>`}</div>
            ${technical.length ? `<div class="text-secondary mb-1" style="font-size:0.65rem;">${t("mvs.other_flags")}</div><div class="d-flex flex-wrap gap-1">${technical.map((f) => flagChip(f, true)).join("")}</div>` : ""}`) : (caps.moves_full ? "" : `<div class="text-secondary small fst-italic mb-3">${t("mvs.flags_hint")}</div>`)}
        </div>
        <div class="col-12 col-lg-6">
          ${propRows.length ? card(t("mvs.details"), "bi-gear-fill", propRows.map(([l, v]) => infoRow(l, v)).join("")) : ""}
          ${card(t("mvs.learners_title", { n: learners.length }), "bi-people-fill", `
            ${hasLearnSources ? `<div class="form-check form-switch small mb-2"><input class="form-check-input" type="checkbox" role="switch" id="learners-gen9" ${learnersGen9 ? "checked" : ""}><label class="form-check-label text-secondary" for="learners-gen9">${t("mvs.gen9_only")}</label></div>` : ""}
            <div id="learners-host">${pokemonChipList(filterLearners(learners, hasLearnSources && learnersGen9), { id: "learners-chips" })}</div>`)}
        </div>
      </div>`;

    if (hasLearnSources) {
      const toggle = document.getElementById("learners-gen9");
      toggle.addEventListener("change", () => {
        learnersGen9 = toggle.checked;
        document.getElementById("learners-host").innerHTML = pokemonChipList(filterLearners(learners, toggle.checked), { id: "learners-chips" });
      });
    }
  }

  function filterLearners(learners, gen9Only) {
    if (!gen9Only) return learners;
    return learners.filter((l) => !l.sources || !l.sources.length || learnSummary(l.sources).inPreferred);
  }

  /* ------------------------------------------------------------------ */
  /* FICHA: OBJETO                                                       */
  /* ------------------------------------------------------------------ */
  function renderItem(d) {
    const color = itemCatColor(d.category);
    setModalColor(color);
    modalHeader.innerHTML = `
      <span class="it-icon-plate" style="width:56px;height:56px;border-radius:16px;">${itemIconHtml(d, 40)}</span>
      <div>
        <h5 class="modal-title fw-bold text-light mb-0">${esc(dn("item", d))}${d.num ? ` <span class="dex-num ms-1">No.${esc(d.num)}</span>` : ""}</h5>
        ${subName("item", d) ? `<div class="text-secondary" style="font-size:0.72rem;">${esc(d.name)}</div>` : ""}
        <div class="d-flex flex-wrap gap-1 mt-1"><span class="badge" style="background:${color};color:#0b1020;">${esc(itemCatLabel(d.category))}</span> ${d.is_past ? pastBadge() : ""}</div>
      </div>`;

    const props = d.properties || {};
    const propRows = [];
    if (props.fling) propRows.push([t("it.fling"), t("it.fling_v", { n: props.fling.basePower ?? "—" }) + (props.fling.status ? " · " + t("mp.sec_status", { x: statusLabel(props.fling.status) }) : "") + (props.fling.volatileStatus ? " · " + esc(props.fling.volatileStatus) : "")]);
    if (props.naturalGift) propRows.push([t("it.natgift"), t("it.natgift_v", { n: props.naturalGift.basePower, t: typeName(props.naturalGift.type) })]);
    if (props.onPlate) propRows.push([t("it.plate"), esc(props.onPlate)]);
    if (props.onMemory) propRows.push([t("it.memory"), esc(props.onMemory)]);
    if (props.onDrive) propRows.push([t("it.drive"), esc(props.onDrive)]);
    if (props.zMoveType) propRows.push([t("it.ztype"), esc(props.zMoveType)]);
    if (props.zMove) propRows.push([t("it.zmove"), esc(typeof props.zMove === "string" ? props.zMove : "—")]);
    if (props.zMoveFrom) propRows.push([t("it.zfrom"), esc(props.zMoveFrom)]);
    if (props.forcedForme) propRows.push([t("it.forced"), esc(props.forcedForme)]);
    if (props.boosts) propRows.push([t("it.boosts"), describeBoosts(props.boosts)]);
    if (d.gen) propRows.push([t("it.introduced"), t("it.gen_n", { n: d.gen })]);
    if (d.mega_evolves) propRows.push([t("it.mega_to"), esc(d.mega_evolves)]);
    propRows.push([t("mvs.avail"), d.is_past ? t("mvs.avail_no") : t("mvs.avail_yes")]);
    if (d.is_choice) propRows.push([t("mvs.type"), t("it.is_choice")]);

    const noExtra = !caps.items_extra;
    modalBody.innerHTML = `
      <div class="row g-3">
        <div class="col-12 col-lg-6">
          ${card(t("it.effect"), "bi-info-circle-fill", `
            ${(descTr("item", d.id) || d.short_desc) ? descBlock(descTr("item", d.id), d.short_desc, d.desc) : `<p class="text-secondary fst-italic">${t("it.no_desc_hint")}</p>`}
            ${d.desc_is_derived && !descTr("item", d.id) ? `<div class="text-secondary" style="font-size:0.68rem;">${t("it.derived")}</div>` : ""}`)}
          ${card(t("it.data"), "bi-sliders", propRows.map(([l, v]) => infoRow(l, v)).join("") + (noExtra ? `<div class="text-secondary fst-italic mt-2" style="font-size:0.68rem;">${t("it.extra_hint")}</div>` : ""))}
        </div>
        <div class="col-12 col-lg-6">
          ${(d.required_by || []).length ? card(t("it.required_by", { n: d.required_by.length }), "bi-lock-fill", pokemonChipList(d.required_by, { id: "req-chips" })) : ""}
          ${(d.users || []).length ? card(t("it.users", { n: d.users.length }), "bi-person-fill", pokemonChipList(d.users, { id: "users-chips" })) : ""}
          ${!(d.required_by || []).length && !(d.users || []).length ? card(t("it.who"), "bi-people-fill", `<div class="text-secondary fst-italic small">${t("it.general")}</div>`) : ""}
        </div>
      </div>`;
  }

  /* ------------------------------------------------------------------ */
  /* FICHA: HABILIDAD                                                    */
  /* ------------------------------------------------------------------ */
  function renderAbility(d) {
    const c = abCat(d.category);
    setModalColor(c.color);
    const tagChips = (d.tags || []).map((id) => {
      const tc = abCat(id);
      return `<span class="ab-chip ab-chip-ghost" style="--ac:${tc.color};"><i class="bi ${tc.icon}"></i>${esc(abCatLabel(id))}</span>`;
    }).join(" ");

    modalHeader.innerHTML = `
      <span class="ab-icon" style="--ac:${c.color};width:56px;height:56px;border-radius:18px;font-size:1.6rem;"><i class="bi ${c.icon}"></i></span>
      <div>
        <h5 class="modal-title fw-bold text-light mb-0">${esc(dn("ability", d))}</h5>
        ${subName("ability", d) ? `<div class="text-secondary small">${esc(d.name)}</div>` : ""}
        <div class="d-flex flex-wrap gap-1 mt-1">
          <span class="ab-chip ab-chip-solid" style="--ac:${c.color};"><i class="bi ${c.icon}"></i>${esc(abCatLabel(d.category))}</span>
          ${tagChips}
        </div>
      </div>`;

    const pick = pickAbilityDesc(d.desc, d.desc_en, d.id);
    const hiddenCount = (d.pokemon || []).filter((p) => p.hidden).length;
    modalBody.innerHTML = `
      <div class="row g-3">
        <div class="col-12 col-lg-5">
          ${card(t("ab.effect"), "bi-info-circle-fill", `
            ${pick.text ? `<p class="text-light mb-2" style="font-size:0.88rem;line-height:1.5;">${esc(pick.text)}</p>` : `<p class="text-secondary fst-italic">${t("ab.no_data_long")}</p>`}
            ${pick.note ? `<div class="text-warning fst-italic" style="font-size:0.7rem;">${esc(pick.note)}</div>` : ""}
            ${pick.other ? `<div class="text-secondary mt-2 pt-2 border-top border-secondary-subtle" style="font-size:0.74rem;"><b>${t("ab.other_lang", { lang: I18N.langLabel(pick.otherLang) })}</b> ${esc(pick.other)}</div>` : ""}`)}
          ${card(t("ab.data"), "bi-sliders", `
            ${infoRow(t("ab.category"), `<span class="ab-chip ab-chip-solid" style="--ac:${c.color};"><i class="bi ${c.icon}"></i>${esc(abCatLabel(d.category))}</span>`)}
            ${infoRow(t("ab.name_en"), esc(d.name))}
            ${subName("ability", d) ? infoRow(t("ab.name_local", { lang: I18N.langLabel() }), esc(dn("ability", d))) : ""}
            ${infoRow(t("ab.count"), (d.pokemon || []).length)}
            ${infoRow(t("ab.hidden_count"), hiddenCount)}`)}
        </div>
        <div class="col-12 col-lg-7">
          ${card(t("ab.pokemon_title", { n: (d.pokemon || []).length }), "bi-people-fill", pokemonChipList(d.pokemon || [], {
            id: "ab-chips",
            extraFn: (p) => (p.hidden ? `<span class="badge bg-warning text-dark" style="font-size:0.55rem;">${t("ab.hidden_tag")}</span>` : "")
          }))}
        </div>
      </div>`;
  }

  const RENDERERS = { pokemon: renderPokemon, move: renderMove, item: renderItem, ability: renderAbility };

  /* ------------------------------------------------------------------ */
  /* Eventos y Sincronización Interactiva                               */
  /* ------------------------------------------------------------------ */
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentTab = btn.getAttribute("data-cat");
      searchInput.value = "";
      setupControls();
      refreshList();
    });
  });

  let searchTimer = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(refreshList, 120);
  });

  filter1.addEventListener("change", () => refreshList());
  filter2.addEventListener("change", () => refreshList());
  sortSel.addEventListener("change", () => refreshList());

  // Delegación de clics universales sobre los chips de la barra inferior
  const legendEl = document.getElementById("compendium-legend");
  if (legendEl) {
    legendEl.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".comp-chip-btn");
      if (!btn) return;
      const target = btn.dataset.target;
      const val = btn.dataset.val;
      const selectEl = target === "filter2" ? filter2 : filter1;

      // Alternar filtro: si ya estaba seleccionado, se desactiva
      selectEl.value = selectEl.value === val ? "" : val;
      refreshList();
    });
  }

  function rerenderDetail() {
    if (!currentDetail || !modalEl.classList.contains("show")) return;
    const bodyEl = modalEl.querySelector(".modal-body");
    const scroll = bodyEl ? bodyEl.scrollTop : 0;
    const activeTab = (modalBody.querySelector(".nav-link.active") || {}).getAttribute
      ? modalBody.querySelector(".nav-link.active").getAttribute("data-bs-target") : null;
    if (currentDetail.kind === "pokemon") renderPokemon(currentDetail.d, true);
    else RENDERERS[currentDetail.kind](currentDetail.d);
    if (activeTab && activeTab !== "#pk-tab-summary") {
      const btn = modalBody.querySelector(`[data-bs-target="${activeTab}"]`);
      if (btn && window.bootstrap) bootstrap.Tab.getOrCreateInstance(btn).show();
    }
    if (bodyEl) requestAnimationFrame(() => { bodyEl.scrollTop = scroll; });
  }

  function rerenderAll() {
    if (!data.pokemon.length) return;
    const scroller = document.getElementById("view-pokedex");
    const keep = { f1: filter1.value, f2: filter2.value, s: sortSel.value, top: scroller ? scroller.scrollTop : 0, shown: renderedCount };
    updateTabLabels();
    showCapabilityNotice();
    setupControls();
    if ([...filter1.options].some((o) => o.value === keep.f1)) filter1.value = keep.f1;
    if ([...filter2.options].some((o) => o.value === keep.f2)) filter2.value = keep.f2;
    if ([...sortSel.options].some((o) => o.value === keep.s)) sortSel.value = keep.s;
    refreshList(keep.shown);
    if (scroller) scroller.scrollTop = keep.top;
    rerenderDetail();
  }

  let langToken = 0;
  document.addEventListener("langchange", async () => {
    const token = ++langToken;
    rerenderAll();
    if (!L10N.isReady(I18N.lang)) {
      await L10N.load(I18N.lang);
      if (token === langToken) rerenderAll();
    }
  });

  initCompendium();
});