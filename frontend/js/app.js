// Variable global accesible por el HTML
let activeFormatTarget = "teambuilder";
let renderFormatColumnsGlobal = null;

window.openFormatModal = function(target) {
  activeFormatTarget = target;
  if (renderFormatColumnsGlobal) {
    renderFormatColumnsGlobal();
  }
  const modal = document.getElementById("format-modal");
  if (modal) {
    modal.classList.remove("d-none");
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const TYPE_CONFIG = {
    normal:   { es: "NORMAL",    icon: "bi-record-circle",    bg: "#919aa2" },
    fire:     { es: "FUEGO",     icon: "bi-fire",             bg: "#ff9741" },
    water:    { es: "AGUA",      icon: "bi-droplet-fill",     bg: "#3692dc" },
    electric: { es: "ELÉCTRICO", icon: "bi-lightning-fill",   bg: "#e5a600" },
    grass:    { es: "PLANTA",    icon: "bi-flower1",          bg: "#38bf4b" },
    ice:      { es: "HIELO",     icon: "bi-snow",             bg: "#4cd1c0" },
    fighting: { es: "LUCHA",     icon: "bi-hammer",           bg: "#ce416b" },
    poison:   { es: "VENENO",    icon: "bi-radioactive",      bg: "#b567ce" },
    ground:   { es: "TIERRA",    icon: "bi-triangle-fill",    bg: "#d97742" },
    flying:   { es: "VOLADOR",   icon: "bi-wind",             bg: "#8fa9de" },
    psychic:  { es: "PSÍQUICO",  icon: "bi-eye-fill",         bg: "#ff6a7a" },
    bug:      { es: "BICHO",     icon: "bi-bug-fill",         bg: "#91c12f" },
    rock:     { es: "ROCA",      icon: "bi-gem",              bg: "#c5b78c" },
    ghost:    { es: "FANTASMA",  icon: "bi-incognito",        bg: "#5269ac" },
    dragon:   { es: "DRAGÓN",    icon: "bi-shield-shaded",    bg: "#006fc9" },
    dark:     { es: "SINIESTRO", icon: "bi-moon-fill",        bg: "#5a5366" },
    steel:    { es: "ACERO",     icon: "bi-gear-fill",        bg: "#5a8ea2" },
    fairy:    { es: "HADA",      icon: "bi-stars",            bg: "#ec8fe6" },
  };

  const CATEGORY_ICON_CLASS = { Physical: "bi-bullseye", Special: "bi-magic", Status: "bi-shield-shaded" };
  function categoryLabel(cat) {
    const label = I18N.has("cat." + cat) ? t("cat." + cat) : cat;
    return `<i class="bi ${CATEGORY_ICON_CLASS[cat] || "bi-circle"} me-1"></i> ${label}`;
  }

  const NATURE_EFFECTS = {
    Adamant: ["atk", "sp_atk"], Brave: ["atk", "speed"], Lonely: ["atk", "defense"], Naughty: ["atk", "sp_def"],
    Bold: ["defense", "atk"], Impish: ["defense", "sp_atk"], Lax: ["defense", "sp_def"], Relaxed: ["defense", "speed"],
    Modest: ["sp_atk", "atk"], Mild: ["sp_atk", "defense"], Quiet: ["sp_atk", "speed"], Rash: ["sp_atk", "sp_def"],
    Calm: ["sp_def", "atk"], Careful: ["sp_def", "sp_atk"], Gentle: ["sp_def", "defense"], Sassy: ["sp_def", "speed"],
    Timid: ["speed", "atk"], Hasty: ["speed", "defense"], Jolly: ["speed", "sp_atk"], Naive: ["speed", "sp_def"],
  };

  const currentFormatLabel = document.getElementById("current-format-label");
  const analyzerFormatLabel = document.getElementById("analyzer-format-label");
  const analyzerFormatIdInput = document.getElementById("analyzer-format-id");

  const formatModal = document.getElementById("format-modal");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const formatSearch = document.getElementById("format-search");
  const genTabs = document.getElementById("gen-tabs");
  const formatColumns = document.getElementById("format-columns");

  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const btnSend = document.getElementById("btn-send");
  const chatMessages = document.getElementById("chat-messages");

  const teamGrid = document.getElementById("team-grid");
  const strategyContent = document.getElementById("strategy-content");
  const btnCopyPaste = document.getElementById("btn-copy-paste");

  const poolTitle = document.getElementById("pool-status-title");
  const poolBadges = document.getElementById("pool-badges");

  let allFormats = [];
  let selectedGen = "9";
  let currentFormatId = "gen9championsvgc2026regmc";
  let currentFormatName = "[Gen 9 Champions] VGC 2026 Reg M-C";
  let lastGeneratedTeam = null;
  let lastStrategyGuide = null;
  let lastEra = null;
  let generationSeq = 0;
  let lastGuideLang = null;
  let chatHistory = []; // conversación con el bot (se reinicia al cambiar de formato)
  let lastTeamFormat = null;

  renderFormatColumnsGlobal = renderFormatColumns;

  initApp();

  async function loadItemIcons() {
    const map = await ApiService.getItemIcons();
    Sprites.setItemMap(map);
    if (lastGeneratedTeam) rerenderTeam();
  }

  async function initApp() {
    renderEmptySlots();
    loadItemIcons();
    if (currentFormatLabel) currentFormatLabel.textContent = formatCurrentLabel(currentFormatName, "9");
    await loadFormatsFromBackend();
    await updateFormatPoolStatus(currentFormatId, false);
  }

  function formatCurrentLabel(name, gen = "9") {
    const clean = name.trim();
    return clean.startsWith("[Gen") ? clean : `[Gen ${gen}] ${clean}`;
  }

  async function loadFormatsFromBackend() {
    try {
      const data = await ApiService.getFormats();
      if (data.formats && data.formats.length > 0) {
        allFormats = data.formats.map((f) => {
          const genMatch = f.id.match(/^gen(\d)/);
          return {
            id: f.id,
            name: f.name,
            gen: genMatch ? genMatch[1] : "9",
            game_type: f.game_type || "doubles",
            category: categorizeFormat(f.id, f.name, f.game_type),
          };
        });
      }
    } catch (err) {
      allFormats = getFallbackFormats();
    }
    renderFormatColumns();
  }

  function categorizeFormat(id, name, gameType) {
    const lower = (id + " " + name).toLowerCase();
    if (lower.includes("champion")) return "Pokémon Champions";
    if (lower.includes("vgc") || lower.includes("bss")) return "VGC & Battle Stadium";
    if (gameType === "doubles" || lower.includes("doubles")) return "Smogon Doubles";
    return "Smogon Singles";
  }

  function getFallbackFormats() {
    return [
      { id: "gen9championsvgc2026regmc", name: "[Gen 9 Champions] VGC 2026 Reg M-C", gen: "9", category: "Pokémon Champions" },
      { id: "gen9vgc2024regh", name: "[Gen 9] VGC 2024 Reg H", gen: "9", category: "VGC & Battle Stadium" },
      { id: "gen8doublesubers", name: "[Gen 8] Doubles Ubers", gen: "8", category: "Smogon Doubles" },
      { id: "gen7ou", name: "[Gen 7] OU", gen: "7", category: "Smogon Singles" },
      { id: "gen9ou", name: "[Gen 9] OU", gen: "9", category: "Smogon Singles" },
    ];
  }

  function renderFormatColumns() {
    if (!formatColumns) return;
    const query = (formatSearch?.value || "").toLowerCase().trim();

    const filtered = allFormats.filter((f) => {
      const matchesGen = query ? true : f.gen === selectedGen;
      return matchesGen && (!query || f.name.toLowerCase().includes(query) || f.id.includes(query));
    });

    const groups = {};
    filtered.forEach((f) => {
      if (!groups[f.category]) groups[f.category] = [];
      groups[f.category].push(f);
    });

    formatColumns.innerHTML = "";
    const categoryOrder = ["Pokémon Champions", "VGC & Battle Stadium", "Smogon Singles", "Smogon Doubles"];

    categoryOrder.forEach((cat) => {
      const list = groups[cat];
      if (!list || list.length === 0) return;

      const col = document.createElement("div");
      col.className = "col-12 col-md-6 col-lg-3";
      col.innerHTML = `
        <h6 class="text-uppercase text-secondary fw-bold border-bottom border-secondary-subtle pb-2 mb-2" style="font-size:0.7rem; letter-spacing:0.5px;">
          ${cat}
        </h6>
        <div class="d-flex flex-column gap-1"></div>
      `;

      const listContainer = col.querySelector("div");
      list.forEach((fmt) => {
        const activeId = activeFormatTarget === 'teambuilder' ? currentFormatId : analyzerFormatIdInput?.value;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `format-option-btn ${fmt.id === activeId ? "selected" : ""}`;
        btn.innerHTML = `<i class="bi bi-chevron-right fs-xs me-1 text-secondary"></i>${fmt.name}`;
        btn.addEventListener("click", () => selectFormat(fmt));
        listContainer.appendChild(btn);
      });

      formatColumns.appendChild(col);
    });
  }

  async function selectFormat(fmt) {
    if (activeFormatTarget === "teambuilder") {
      currentFormatId = fmt.id;
      currentFormatName = fmt.name;
      chatHistory = [];
      if (currentFormatLabel) currentFormatLabel.textContent = formatCurrentLabel(fmt.name, fmt.gen);
      if (formatModal) formatModal.classList.add("d-none");
      renderFormatColumns();
      await updateFormatPoolStatus(currentFormatId, true);
    } else {
      if (analyzerFormatIdInput) analyzerFormatIdInput.value = fmt.id;
      if (analyzerFormatLabel) analyzerFormatLabel.textContent = formatCurrentLabel(fmt.name, fmt.gen);
      if (formatModal) formatModal.classList.add("d-none");
      renderFormatColumns();
    }
  }

  async function updateFormatPoolStatus(formatId, notifyInChat = false) {
    try {
      const pool = await ApiService.getFormatPool(formatId);
      const mech = pool.mechanics || {};

      if (poolTitle && poolBadges) {
        poolTitle.innerHTML = `<i class="bi bi-check-circle-fill text-success"></i> <span>${t("tb.pool", { pk: pool.total_legal_pokemon, it: pool.total_legal_items })}</span>`;

        const genNum = parseInt(mech.gen || 9, 10);
        const badgesHtml = [];

        if (mech.allow_megas) {
          badgesHtml.push(`<span class="badge bg-purple-subtle text-light border border-secondary" style="background:#6b21a8;"><i class="bi bi-dna me-1"></i>${t("tb.badge_megas", { n: mech.max_megas || 1 })}</span>`);
        }
        if (genNum === 7 || (pool.format?.name || "").includes("Gen 7")) {
          badgesHtml.push(`<span class="badge bg-warning-subtle text-warning border border-warning-subtle"><i class="bi bi-lightning-charge-fill me-1"></i>${t("tb.badge_z")}</span>`);
        }
        if (genNum === 8 || (pool.format?.name || "").includes("Gen 8")) {
          badgesHtml.push(`<span class="badge bg-danger-subtle text-danger border border-danger-subtle"><i class="bi bi-cloud-lightning-rain-fill me-1"></i>${t("tb.badge_dmax")}</span>`);
        }
        if (genNum === 9 && mech.allow_tera) {
          badgesHtml.push(`<span class="badge bg-info-subtle text-info border border-info-subtle"><i class="bi bi-gem me-1"></i>${t("tb.badge_tera_on")}</span>`);
        } else if (genNum === 9 && !mech.allow_tera) {
          badgesHtml.push(`<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle"><i class="bi bi-slash-circle me-1"></i>${t("tb.badge_tera_off")}</span>`);
        }
        if (genNum <= 5) {
          badgesHtml.push(`<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle"><i class="bi bi-circle me-1"></i>${t("tb.badge_classic")}</span>`);
        }
        badgesHtml.push(`
          <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">
            ${t("tb.badge_restricted", { n: mech.max_restricted > 0 ? t("tb.max_n", { n: mech.max_restricted }) : "0" })}
          </span>
        `);

        poolBadges.innerHTML = badgesHtml.join(" ");
      }

      if (notifyInChat) {
        appendMessage(
          `${t("tb.fmt_updated", { name: pool.format.name })}<br>` +
            `<small class="text-secondary">${t("tb.fmt_available", { pk: pool.total_legal_pokemon, it: pool.total_legal_items })}<br>` +
            `${t("tb.fmt_params", { megas: mech.allow_megas ? t("tb.megas_on") : t("tb.megas_off"), tera: mech.allow_tera ? t("tb.tera_on") : t("tb.tera_off") })}</small>`,
          "assistant"
        );
      }
    } catch (err) {
      console.error("Error obteniendo pool:", err);
    }
  }

  if (btnCloseModal) btnCloseModal.addEventListener("click", () => formatModal.classList.add("d-none"));
  if (formatModal) {
    formatModal.addEventListener("click", (e) => {
      if (e.target === formatModal) formatModal.classList.add("d-none");
    });
  }
  if (formatSearch) formatSearch.addEventListener("input", renderFormatColumns);

  if (genTabs) {
    genTabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab-btn");
      if (!btn) return;
      genTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedGen = btn.dataset.gen;
      renderFormatColumns();
    });
  }

  // Conversación: historial + equipo actual (solo si es del mismo formato) para poder pedir cambios
  const escHtml = (v) => String(v || "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m]));

  if (chatForm) {
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const promptText = userInput.value.trim();
      if (!promptText) return;

      appendMessage(escHtml(promptText), "user");
      userInput.value = "";
      btnSend.disabled = true;
      chatHistory.push({ role: "user", content: promptText });

      const loadingMsg = appendMessage(
        `<span class="spinner-border spinner-border-sm text-info me-1" role="status"></span> ${t("tb.thinking")}`,
        "assistant"
      );

      const seq = ++generationSeq;
      try {
        const team = lastGeneratedTeam && lastTeamFormat === currentFormatId ? lastGeneratedTeam : null;
        const res = await ApiService.chat(currentFormatId, chatHistory, team);
        if (seq !== generationSeq) return;
        chatHistory.push({ role: "assistant", content: res.reply || "" });

        let html = escHtml(res.reply).replace(/\n/g, "<br>");
        const tr = res.team_result;
        if (tr && Array.isArray(tr.team)) {
          lastEra = tr.era || null;
          lastGeneratedTeam = tr.team;
          lastStrategyGuide = tr.strategy_guide;
          lastGuideLang = tr.lang || I18N.lang;
          lastTeamFormat = currentFormatId;
          await rerenderTeam();
          if (seq !== generationSeq) return;
          renderStrategyGuide(tr.strategy_guide);
          if (window.matchMedia("(max-width: 991.98px)").matches && teamGrid) {
            teamGrid.scrollIntoView({ behavior: "smooth", block: "start" });
          }
          html = `<i class="bi bi-check2-circle text-success me-1"></i> ${html || t("tb.done", { format: currentFormatName })}`;
          if (tr.notes && tr.notes.length) {
            html += `<ul class="small text-secondary mt-2 mb-0 ps-3">${tr.notes.map((n) => `<li>${escHtml(n)}</li>`).join("")}</ul>`;
          }
        } else if (res.error) {
          html = `<i class="bi bi-shield-exclamation text-warning me-1"></i> ${html}`;
        }
        loadingMsg.innerHTML = html;
      } catch (err) {
        if (seq !== generationSeq) return;
        chatHistory.pop();
        loadingMsg.innerHTML = `<i class="bi bi-shield-exclamation text-warning me-1"></i> <span class="text-light-emphasis">${escHtml(err.message)}</span>`;
      } finally {
        btnSend.disabled = false;
        scrollToBottom();
      }
    });
  }

  function appendMessage(html, sender = "assistant") {
    const div = document.createElement("div");
    div.className = `msg ${sender} shadow-sm`;
    div.innerHTML = html;
    chatMessages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    }, 40);
  }

  const STAT_I18N = { hp: "hp", atk: "atk", defense: "def", sp_atk: "spa", sp_def: "spd", speed: "spe" };
  const NEUTRAL_NATURES = ["Hardy", "Docile", "Serious", "Bashful", "Quirky"];

  function typeLabel(typeName) {
    const key = String(typeName || "normal").toLowerCase();
    return I18N.has("type." + key) ? t("type." + key).toUpperCase() : String(typeName || "").toUpperCase();
  }

  function renderTypeBadge(typeName) {
    const key = (typeName || "normal").toLowerCase();
    const conf = TYPE_CONFIG[key] || { icon: "bi-circle", bg: "#64748b" };
    return `<span class="type-badge-pill" style="background-color: ${conf.bg};"><i class="bi ${conf.icon}"></i> ${typeLabel(typeName)}</span>`;
  }

  function typeColor(typeName) {
    const conf = TYPE_CONFIG[(typeName || "").toLowerCase()];
    return conf ? conf.bg : "#64748b";
  }

  function natureDescription(nature, fallback) {
    if (NEUTRAL_NATURES.includes(nature)) return t("nat.neutral");
    const eff = NATURE_EFFECTS[nature];
    if (!eff) return fallback;
    const name = (k) => t("stat." + STAT_I18N[k]);
    return t("nat.effect", { plus: name(eff[0]), minus: name(eff[1]) });
  }

  function localizedDetails(details, poke, loc) {
    const out = { ...details };

    const getTr = (kind, raw, fallbackDesc, isHistorical) => {
        const id = raw ? String(raw).toLowerCase().replace(/[^a-z0-9]/g, "") : "";
        
        let tr = "";
        if (window.L10N && window.L10N.desc) {
            tr = window.L10N.desc(kind, id);
        }

        if (isHistorical) {
            const esOverride = /aumenta|reduce|potencia|daño|restaura|usuario|objetivo|fuerza/i.test(fallbackDesc);
            if (esOverride) return fallbackDesc;
        }

        return tr || fallbackDesc || "";
    };

    const getName = (kind, raw) => {
        const id = raw ? String(raw).toLowerCase().replace(/[^a-z0-9]/g, "") : "";
        if (window.L10N && typeof window.L10N.nameOf === "function") {
            const nameTr = window.L10N.nameOf(kind, raw);
            if (nameTr) return nameTr;
        }
        return raw;
    };

    out.ability_name = getName("ability", poke.ability);
    out.item_name = poke.item ? getName("item", poke.item) : "";
    
    out.ability_desc = getTr("ability", poke.ability, details.ability_desc, false);
    out.item_desc = getTr("item", poke.item, details.item_desc, false);
    out.nature_desc = natureDescription(poke.nature, details.nature_desc);

    out.moves_info = (details.moves_info || []).map((m) => {
        return {
            ...m,
            locName: getName("move", m.name),
            desc: getTr("move", m.name, m.desc, m.is_historical)
        };
    });

    return out;
  }

  async function loadLocalizedDescriptions(team, gen) {
    if (I18N.lang === "es" || !Array.isArray(team)) return null;
    const abilities = [], items = [], moves = [];
    team.forEach((p) => {
      if (p.ability) abilities.push(p.ability);
      if (p.item) items.push(p.item);
      const infos = (p.details && p.details.moves_info) || [];
      if (infos.length) {
          infos.forEach((m) => moves.push(m.name));
      } else if (p.moves) {
          p.moves.forEach((m) => moves.push(m));
      }
    });
    return await ApiService.describeTerms(abilities, items, moves);
  }

  async function rerenderTeam() {
    if (!lastGeneratedTeam) return;
    const inferredGen = lastEra ? lastEra.gen : 9;
    const loc = await loadLocalizedDescriptions(lastGeneratedTeam, inferredGen);
    renderTeamGrid(lastGeneratedTeam, loc);
  }

  function evPlanLine(plan) {
    if (!plan) return "";
    let text;
    if (plan.source === "custom") {
      text = t("ev.custom");
    } else if (plan.source === "usage") {
      text = t("ev.usage");
    } else {
      const sp = plan.speed || {};
      const parts = [t("ev.role_" + plan.role)];
      if (sp.mode === "tier") parts.push(t(sp.scarf ? "ev.speed_scarf" : "ev.speed_tier", { n: sp.beats_base }));
      else if (sp.mode === "tailwind") parts.push(t("ev.speed_tailwind"));
      else if (sp.mode === "weather") parts.push(t("ev.speed_weather"));
      else parts.push(t("ev.speed_none"));
      text = parts.join(" · ");
    }
    return `<span class="d-block text-secondary fst-italic mt-1" style="font-size:0.66rem;"><i class="bi bi-bullseye me-1"></i>${text}</span>`;
  }

  function renderEmptySlots() {
    if (!teamGrid || lastGeneratedTeam) return;
    teamGrid.innerHTML = [1, 2, 3, 4, 5, 6].map((n) => `
      <div class="card empty-slot-card text-center p-4">
        <i class="bi bi-plus-circle text-secondary fs-2 mb-2"></i>
        <span class="text-secondary small fw-semibold">${t("tb.slot", { n })}</span>
      </div>`).join("");
  }

  function renderTeamGrid(team, loc = null, target = teamGrid, ctx = {}) {
    if (!target || !Array.isArray(team)) return;
    target.innerHTML = "";

    const genMatch = (ctx.formatId || currentFormatId || "").match(/^gen(\d)/i);
    const inferredGen = genMatch ? parseInt(genMatch[1], 10) : 9;
    const fallbackEra = {
      gen: inferredGen,
      has_abilities: inferredGen >= 3,
      has_items: inferredGen >= 2,
      has_natures: inferredGen >= 3,
      modern_evs: inferredGen >= 3,
      stat_level: inferredGen <= 2 ? 100 : 50,
    };
    const E = ctx.era || lastEra || fallbackEra;

    team.forEach((poke, index) => {
      const card = document.createElement("div");
      card.className = "card pokemon-card pk-ballmark";
      card.style.setProperty("--tc", typeColor((poke.types || [])[0]));

      const typesHtml = (poke.types || []).map((tp) => renderTypeBadge(tp)).join(" ");

      let mechanicBadgeHtml = "";
      const speciesLower = (poke.species || "").toLowerCase();
      const itemLower = (poke.item || "").toLowerCase();

      const isMega = speciesLower.includes("mega");
      const isZCrystal = itemLower.endsWith("ium z") || itemLower.endsWith(" z") || itemLower.includes("z-crystal");
      const isGmax = speciesLower.includes("gmax") || speciesLower.includes("gigantamax");

      if (isMega) {
        mechanicBadgeHtml = `<span class="type-badge-pill" style="background:#7c3aed; border: 1px solid #a78bfa;"><i class="bi bi-dna"></i> MEGA</span>`;
      } else if (isZCrystal) {
        mechanicBadgeHtml = `<span class="type-badge-pill" style="background:#d97706; border: 1px solid #fbbf24;"><i class="bi bi-lightning-charge-fill"></i> ${t("card.zcrystal")}</span>`;
      } else if (isGmax) {
        mechanicBadgeHtml = `<span class="type-badge-pill" style="background:#dc2626; border: 1px solid #f87171;"><i class="bi bi-cloud-lightning-rain-fill"></i> G-MAX</span>`;
      } else if (poke.tera_type) {
        mechanicBadgeHtml = `<span class="type-badge-pill" style="background:#0284c7; border: 1px solid #38bdf8;"><i class="bi bi-gem"></i> ${t("card.tera", { type: typeLabel(poke.tera_type) })}</span>`;
      }

      const rawEvs = poke.evs || {};
      const statKeys = ["hp", "atk", "defense", "sp_atk", "sp_def", "speed"];
      const evs252 = {};
      const evs32 = {};
      statKeys.forEach((k) => {
        const v = rawEvs[k] || 0;
        evs252[k] = v;
        evs32[k] = v <= 0 ? 0 : v >= 248 ? 32 : v <= 12 ? 2 : Math.max(1, Math.min(32, Math.round((v + 4) / 8)));
      });

      const sl = (k) => t("ss." + STAT_I18N[k]);
      const evsText = (e) => statKeys.map((k) => `${sl(k)} ${e[k]}`).join(" | ");
      const evs252Text = evsText(evs252);
      const evs32Text = evsText(evs32);

      const baseStats = poke.base_stats || { hp: 80, atk: 80, defense: 80, sp_atk: 80, sp_def: 80, speed: 80 };
      const finalStats = poke.final_stats || { hp: 155, atk: 110, defense: 100, sp_atk: 100, sp_def: 100, speed: 110 };
      const matchups = poke.defensive_matchups || { x4: [], x2: [], x1: [], x05: [], x025: [], x0: [] };
      const rawDetails = poke.details || {
        item_desc: t("card.item_fallback"),
        ability_desc: t("card.ability_fallback"),
        nature_desc: t("card.nature_fallback"),
        moves_info: (poke.moves || []).map((m) => ({
          name: m, type: "Normal", category: "Physical", basePower: 80, accuracy: "100%", priority: 0, desc: t("card.move_fallback"),
        })),
      };
      
      const details = localizedDetails(rawDetails, poke, loc);
      const abilityName = details.ability_name || poke.ability;
      const itemName = details.item_name || poke.item || t("card.no_item");

      const [plusStat, minusStat] = NATURE_EFFECTS[poke.nature] || ["", ""];

      const buildStatRow = (label, key) => {
        const baseVal = baseStats[key] ?? 80;
        const finalVal = finalStats[key] ?? 100;
        const evVal = evs252[key] || 0;
        const pct = Math.min(100, Math.round((baseVal / 180) * 100));

        let barColor = "#38bdf8";
        if (baseVal >= 125) barColor = "#10b981";
        else if (baseVal >= 95) barColor = "#22c55e";
        else if (baseVal >= 70) barColor = "#eab308";
        else if (baseVal < 55) barColor = "#ef4444";

        let natClass = "";
        let natSign = "";
        if (key === plusStat) { natSign = "+"; natClass = "nat-plus"; }
        else if (key === minusStat) { natSign = "-"; natClass = "nat-minus"; }

        return `
          <div class="sd-stat-row">
            <span class="sd-stat-label">${label}</span>
            <span class="sd-stat-base">${baseVal}</span>
            <div class="sd-bar-track">
              <div class="sd-bar-fill" style="width:${pct}%; background:${barColor};"></div>
            </div>
            <span class="sd-stat-ev">${evVal > 0 ? "+" + evVal : ""}</span>
            <span class="sd-stat-final ${natClass}">${finalVal}${natSign}</span>
          </div>
        `;
      };

      const bstTotal = Object.values(baseStats).reduce((a, b) => a + b, 0);
      const formatMatchupList = (arr) => arr && arr.length > 0 ? arr.map((tp) => renderTypeBadge(tp)).join(" ") : `<span class="text-secondary fst-italic" style="font-size:0.68rem;">${t("common.none")}</span>`;

      const movesHtml = (details.moves_info || []).map((mInfo, mIdx) =>
        `<div class="move-pill interactive-move" data-move-idx="${mIdx}">
          <span class="text-truncate">${mInfo.locName || mInfo.name}</span>
        </div>`
      ).join("");

      const movesEffectsHtml = (details.moves_info || []).map((mInfo) => {
        const catBadge = categoryLabel(mInfo.category);
        const bpText = mInfo.basePower > 0 ? `${t("move.pow")}: ${mInfo.basePower}` : t("cat.Status");
        const prioText = mInfo.priority !== 0 ? ` | ${t("move.prio")}: ${mInfo.priority > 0 ? "+" + mInfo.priority : mInfo.priority}` : "";
        return `
          <div class="effect-card">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-1 mb-1">
              <span class="fw-bold text-light">${mInfo.locName || mInfo.name}</span>
              <div class="d-flex gap-1 align-items-center flex-wrap">
                ${renderTypeBadge(mInfo.type)}
                <span class="badge cat-${mInfo.category}" style="font-size:0.62rem;">${catBadge}</span>
                <span class="badge bg-dark border border-secondary-subtle" style="font-size:0.62rem;">${bpText} | ${t("move.acc")}: ${mInfo.accuracy}${prioText}</span>
              </div>
            </div>
            <div class="text-secondary small" style="font-size:0.71rem;">${mInfo.desc}</div>
          </div>
        `;
      }).join("");

      const itemRow = E.has_items ? `<div class="d-flex align-items-center gap-1 flex-wrap"><strong class="text-secondary">${t("card.item")}:</strong> <span class="interactive-term pk-item-inline" data-inspect="item">${Sprites.item(poke.item, 22)} ${itemName} <i class="bi bi-info-circle ms-1 text-info"></i></span></div>` : "";
      const abilityRow = E.has_abilities ? `<div><strong class="text-secondary">${t("card.ability")}:</strong> <span class="interactive-term" data-inspect="ability">${abilityName} <i class="bi bi-info-circle ms-1 text-info"></i></span></div>` : "";
      const natureRow = E.has_natures ? `<div><strong class="text-secondary">${t("card.nature")}:</strong> <span class="interactive-term" data-inspect="nature">${poke.nature} <i class="bi bi-info-circle ms-1 text-info"></i></span></div>` : "";
      const evBlock = E.modern_evs
        ? `<div class="mt-1 pt-1 border-top border-secondary-subtle"><span class="d-block" style="font-size:0.70rem;"><strong>EVs (252):</strong> ${evs252Text}</span><span class="d-block text-info" style="font-size:0.70rem;"><strong>Champions (32):</strong> ${evs32Text}</span>${evPlanLine(poke.ev_plan)}</div>`
        : `<div class="mt-1 pt-1 border-top border-secondary-subtle"><span class="d-block text-info" style="font-size:0.70rem;">${t("card.stats_classic")}</span></div>`;

      const metaBox = `<div class="poke-meta-box d-flex flex-column gap-1 mb-2">${itemRow}${abilityRow}${natureRow}${evBlock}</div>`;
      const abilityEffectCard = E.has_abilities ? `<div class="effect-card"><div class="d-flex justify-content-between align-items-center mb-1"><span class="fw-bold text-light"><i class="bi bi-stars text-info me-1"></i>${abilityName}</span><span class="badge bg-secondary-subtle text-secondary" style="font-size:0.62rem;">${t("card.ability")}</span></div><div class="text-secondary small" style="font-size:0.71rem;">${details.ability_desc}</div></div>` : "";
      const itemEffectCard = E.has_items ? `<div class="effect-card"><div class="d-flex justify-content-between align-items-center mb-1"><span class="fw-bold text-light d-inline-flex align-items-center gap-2">${Sprites.item(poke.item, 22)} ${itemName}</span><span class="badge bg-secondary-subtle text-secondary" style="font-size:0.62rem;">${t("card.item")}</span></div><div class="text-secondary small" style="font-size:0.71rem;">${details.item_desc}</div></div>` : "";
      const natureEffectCard = E.has_natures ? `<div class="effect-card"><div class="d-flex justify-content-between align-items-center mb-1"><span class="fw-bold text-light"><i class="bi bi-dna text-primary me-1"></i>${poke.nature}</span><span class="badge bg-secondary-subtle text-secondary" style="font-size:0.62rem;">${t("card.nature")}</span></div><div class="text-secondary small" style="font-size:0.71rem;">${details.nature_desc}</div></div>` : "";

      const firstMove = (details.moves_info && details.moves_info[0]) || null;
      const defaultInspectorTitle = E.has_abilities
        ? `<i class="bi bi-stars me-1"></i>${t("card.ability")}: ${abilityName}`
        : (firstMove ? `<i class="bi bi-lightning-charge-fill text-danger me-1"></i>${firstMove.locName || firstMove.name}` : `<i class="bi bi-info-circle me-1"></i>${t("tb.inspect_hint")}`);
      const defaultInspectorBody = E.has_abilities
        ? details.ability_desc
        : (firstMove ? firstMove.desc : "");

      card.innerHTML = `
        <div class="d-flex align-items-center gap-3">
          ${Sprites.pokemon(poke.species, 66, "poke-sprite shadow-sm")}
          <div class="flex-grow-1 overflow-hidden">
            <h5 class="fw-bold text-light mb-0 text-truncate" style="font-size:1.05rem;">${poke.species}</h5>
            <small class="text-info fw-semibold d-block text-truncate" style="font-size:0.72rem;">${poke.role || t("card.role_default")}</small>
          </div>
        </div>

        <div class="d-flex flex-wrap gap-1 mt-1">
          ${typesHtml}
          ${mechanicBadgeHtml}
        </div>

        <div class="card-nav-tabs" data-card-idx="${index}">
          <button type="button" class="card-nav-btn active" data-target="set"><i class="bi bi-crosshair me-1"></i>${t("card.tab_set")}</button>
          <button type="button" class="card-nav-btn" data-target="effects"><i class="bi bi-journal-text me-1"></i>${t("card.tab_effects")}</button>
          <button type="button" class="card-nav-btn" data-target="stats"><i class="bi bi-bar-chart-fill me-1"></i>${t("card.tab_stats")}</button>
          <button type="button" class="card-nav-btn" data-target="weakness"><i class="bi bi-shield-fill-check me-1"></i>${t("card.tab_types")}</button>
        </div>

        <div class="card-pane pane-set">
          ${metaBox}

          <div class="moves-grid">
            ${movesHtml}
          </div>

          <div class="quick-inspector shadow-sm">
            <div class="d-flex justify-content-between align-items-center mb-1">
              <span class="fw-bold text-info quick-inspector-title">${defaultInspectorTitle}</span>
              <small class="text-secondary" style="font-size:0.62rem;">${(E.has_items || E.has_abilities || E.has_natures) ? t("card.click_hint") : ""}</small>
            </div>
            <div class="quick-inspector-body text-light-emphasis">${defaultInspectorBody}</div>
          </div>
        </div>

        <div class="card-pane pane-effects d-none">
          <div class="effects-list">
            ${abilityEffectCard}${itemEffectCard}${natureEffectCard}
            ${movesEffectsHtml}
          </div>
        </div>

        <div class="card-pane pane-stats d-none">
          <div class="showdown-stats-table">
            <div class="d-flex justify-content-between text-secondary border-bottom border-secondary-subtle pb-1 mb-1" style="font-size:0.66rem;">
              <span>${t("card.stat_col")}</span>
              <span>${E.modern_evs ? t("card.evs_lv50") : t("card.stats_lv100")}</span>
            </div>
            ${buildStatRow(t("stat.hp"), "hp")}
            ${buildStatRow(t("stat.atk"), "atk")}
            ${buildStatRow(t("stat.def"), "defense")}
            ${buildStatRow(t("stat.spa"), "sp_atk")}
            ${buildStatRow(t("stat.spd"), "sp_def")}
            ${buildStatRow(t("stat.spe"), "speed")}
            <div class="d-flex justify-content-between text-secondary border-top border-secondary-subtle pt-1 mt-1" style="font-size:0.68rem;">
              <span><strong>BST:</strong> ${bstTotal}</span>
              ${E.has_natures ? `<span><strong>${t("card.nat_short")}:</strong> ${poke.nature}</span>` : ""}
            </div>
          </div>
        </div>

        <div class="card-pane pane-weakness d-none">
          <div class="wikidex-table">
            <div class="wk-row wk-x4">
              <div class="wk-label"><span class="wk-mult m-x4">x4</span> ${t("match.x4")}</div>
              <div class="d-flex flex-wrap gap-1">${formatMatchupList(matchups.x4)}</div>
            </div>
            <div class="wk-row wk-x2">
              <div class="wk-label"><span class="wk-mult m-x2">x2</span> ${t("match.x2")}</div>
              <div class="d-flex flex-wrap gap-1">${formatMatchupList(matchups.x2)}</div>
            </div>
            <div class="wk-row wk-x1">
              <div class="wk-label"><span class="wk-mult m-x1">x1</span> ${t("match.x1")}</div>
              <div class="d-flex flex-wrap gap-1">${formatMatchupList(matchups.x1)}</div>
            </div>
            <div class="wk-row wk-x05">
              <div class="wk-label"><span class="wk-mult m-x05">½</span> ${t("match.x05")}</div>
              <div class="d-flex flex-wrap gap-1">${formatMatchupList(matchups.x05)}</div>
            </div>
            <div class="wk-row wk-x025">
              <div class="wk-label"><span class="wk-mult m-x025">¼</span> ${t("match.x025")}</div>
              <div class="d-flex flex-wrap gap-1">${formatMatchupList(matchups.x025)}</div>
            </div>
            <div class="wk-row wk-x0">
              <div class="wk-label"><span class="wk-mult m-x0">0</span> ${t("match.x0")}</div>
              <div class="d-flex flex-wrap gap-1">${formatMatchupList(matchups.x0)}</div>
            </div>
          </div>
        </div>
      `;

      const tabs = card.querySelectorAll(".card-nav-btn");
      const panes = {
        set: card.querySelector(".pane-set"),
        effects: card.querySelector(".pane-effects"),
        stats: card.querySelector(".pane-stats"),
        weakness: card.querySelector(".pane-weakness"),
      };

      tabs.forEach((btn) => {
        btn.addEventListener("click", () => {
          tabs.forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          const target = btn.dataset.target;
          Object.values(panes).forEach((p) => p.classList.add("d-none"));
          panes[target].classList.remove("d-none");
        });
      });

      const insTitle = card.querySelector(".quick-inspector-title");
      const insBody = card.querySelector(".quick-inspector-body");

      card.querySelectorAll(".interactive-term").forEach((el) => {
        const updateInfo = () => {
          const kind = el.dataset.inspect;
          if (kind === "item" && E.has_items) {
            insTitle.innerHTML = `<span class="d-inline-flex align-items-center gap-1">${Sprites.item(poke.item, 20)} ${t("card.item")}: ${itemName}</span>`;
            insBody.textContent = details.item_desc;
          } else if (kind === "ability" && E.has_abilities) {
            insTitle.innerHTML = `<i class="bi bi-stars text-info me-1"></i>${t("card.ability")}: ${abilityName}`;
            insBody.textContent = details.ability_desc;
          } else if (kind === "nature" && E.has_natures) {
            insTitle.innerHTML = `<i class="bi bi-dna text-primary me-1"></i>${t("card.nature")}: ${poke.nature}`;
            insBody.textContent = details.nature_desc;
          }
        };
        el.addEventListener("click", updateInfo);
        el.addEventListener("mouseenter", updateInfo);
      });

      card.querySelectorAll(".interactive-move").forEach((mvEl) => {
        const updateMove = () => {
          const mIdx = parseInt(mvEl.dataset.moveIdx, 10);
          const mInfo = (details.moves_info || [])[mIdx];
          if (!mInfo) return;
          
          const bpText = mInfo.basePower > 0 ? `${t("move.pow")}: ${mInfo.basePower}` : t("cat.Status");
          
          insTitle.innerHTML = `<i class="bi bi-lightning-charge-fill text-danger me-1"></i>${mInfo.locName || mInfo.name} <span class="badge bg-dark border border-secondary-subtle ms-1" style="font-size:0.62rem;">${typeLabel(mInfo.type)} | ${bpText} | ${t("move.acc")}: ${mInfo.accuracy}</span>`;
          insBody.textContent = mInfo.desc;
        };
        mvEl.addEventListener("click", updateMove);
        mvEl.addEventListener("mouseenter", updateMove);
      });

      target.appendChild(card);
    });
  }

  function renderStrategyGuide(guide, box = strategyContent, guideLang = lastGuideLang) {
    if (!box || !guide) return;
    if (guide.error) {
      const safe = String(guide.error).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
      box.innerHTML = `<div class="alert alert-warning py-2 px-3 small mb-0"><i class="bi bi-exclamation-triangle-fill me-1"></i>${t("tb.guide_error", { msg: safe })}</div>`;
      return;
    }

    let planText = guide.turn_by_turn_plan || "";
    if (typeof planText === "object" && planText !== null) {
      planText = Object.entries(planText).map(([k, v]) => `<strong>${k}:</strong> ${v}`).join(" ");
    }

    const threatsHtml = Array.isArray(guide.threats_to_watch)
      ? guide.threats_to_watch.map((th) => `<li class="mb-1">${th}</li>`).join("")
      : "";

    const staleNote = guideLang && guideLang !== I18N.lang
      ? `<div class="text-warning fst-italic" style="font-size:0.72rem;"><i class="bi bi-translate me-1"></i>${t("tb.lang_note", { lang: I18N.langLabel() })}</div>`
      : "";

    const escHtml = (s) => {
      const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
      return String(s).replace(/[&<>"']/g, (m) => map[m]);
    };

    if (Array.isArray(guide.sections) && guide.sections.length) {
      const titles = { core: "strat.sec_core", leads: "strat.sec_leads", win_condition: "strat.sec_win", threats: "strat.sec_threats" };
      const icons = { core: "bi-link-45deg", leads: "bi-play-circle-fill", win_condition: "bi-trophy-fill", threats: "bi-shield-exclamation" };
      
      let sectionsHtml = "";
      guide.sections.forEach(s => {
        let secTitle = t(titles[s.key] || "strat.sec_core");
        let secIcon = icons[s.key] || "bi-dot";
        sectionsHtml += `
          <div class="strat-section">
            <div class="strat-title"><i class="bi ${secIcon} me-1"></i>${secTitle}</div>
            <div class="text-light-emphasis">${escHtml(s.text)}</div>
          </div>
        `;
      });

      box.innerHTML = `
        <div class="d-flex flex-column gap-2 small">
          ${staleNote}
          <div><strong class="text-info"><i class="bi bi-crosshair2 me-1"></i>${t("strat.style")}</strong> <span class="badge bg-primary-subtle text-primary border border-primary-subtle">${escHtml(guide.gameplay_mode || t("card.role_default"))}</span></div>
          ${sectionsHtml}
        </div>`;
      return;
    }
    
    if (Array.isArray(guide.bullets) && guide.bullets.length) {
      let bulletsHtml = "";
      guide.bullets.forEach(b => {
        bulletsHtml += `<li class="mb-1">${escHtml(b)}</li>`;
      });
      box.innerHTML = `
        <div class="d-flex flex-column gap-2 small">
          ${staleNote}
          <div><strong class="text-info"><i class="bi bi-crosshair2 me-1"></i>${t("strat.style")}</strong> <span class="badge bg-primary-subtle text-primary border border-primary-subtle">${escHtml(guide.gameplay_mode || t("card.role_default"))}</span></div>
          <ul class="text-light-emphasis mb-0 ps-3 strat-bullets">${bulletsHtml}</ul>
        </div>`;
      return;
    }

    box.innerHTML = `
      <div class="d-flex flex-column gap-2 small">
        ${staleNote}
        <div><strong class="text-info"><i class="bi bi-crosshair2 me-1"></i>${t("strat.style")}</strong> <span class="badge bg-primary-subtle text-primary border border-primary-subtle">${guide.gameplay_mode || t("card.role_default")}</span></div>
        <div><strong class="text-info"><i class="bi bi-link-45deg me-1"></i>${t("strat.core")}</strong> <span class="text-light-emphasis">${guide.core_concept || ""}</span></div>
        <div><strong class="text-info"><i class="bi bi-play-circle-fill me-1"></i>${t("strat.plan")}</strong> <span class="text-light-emphasis">${planText}</span></div>
        ${threatsHtml ? `<div class="mt-2"><strong class="text-warning"><i class="bi bi-shield-exclamation me-1"></i>${t("strat.threats")}</strong><ul class="text-light-emphasis mt-1 ps-3 mb-0">${threatsHtml}</ul></div>` : ""}
      </div>
    `;
  }

  function copyTeamToShowdown() {
    if (!lastGeneratedTeam || lastGeneratedTeam.length === 0) {
      alert(t("tb.copy_first"));
      return;
    }

    const statLabels = { hp: "HP", atk: "Atk", defense: "Def", sp_atk: "SpA", sp_def: "SpD", speed: "Spe" };
    const showdownText = lastGeneratedTeam
      .map((p) => {
        const lines = [];
        lines.push(p.item ? `${p.species} @ ${p.item}` : p.species);
        if (p.ability) lines.push(`Ability: ${p.ability}`);
        if (p.tera_type) lines.push(`Tera Type: ${p.tera_type}`);

        const evParts = [];
        Object.entries(p.evs || {}).forEach(([k, val]) => {
          if (val > 0 && statLabels[k]) evParts.push(`${val} ${statLabels[k]}`);
        });
        if (evParts.length > 0) lines.push(`EVs: ${evParts.join(" / ")}`);

        if (p.nature) lines.push(`${p.nature} Nature`);
        const mList = p.moves || [];
        mList.forEach((m) => lines.push(`- ${m}`));
        return lines.join("\n");
      })
      .join("\n\n");

    navigator.clipboard.writeText(showdownText).then(() => {
      if (btnCopyPaste) {
        const origDesktop = btnCopyPaste.innerHTML;
        btnCopyPaste.innerHTML = '<i class="bi bi-check-lg text-success"></i> <span>' + t("tb.copied") + '</span>';
        setTimeout(() => { btnCopyPaste.innerHTML = origDesktop; I18N.apply(btnCopyPaste); }, 2500);
      }
    });
  }

  if (btnCopyPaste) btnCopyPaste.addEventListener("click", copyTeamToShowdown);

  // Botones para subir / bajar en el chat; solo aparecen cuando hay algo que recorrer
  (function setupChatScrollButtons() {
    const box = document.getElementById("chat-messages");
    const up = document.getElementById("chat-scroll-top");
    const down = document.getElementById("chat-scroll-bottom");
    if (!box || !up || !down) return;
    const update = () => {
      const max = box.scrollHeight - box.clientHeight;
      up.classList.toggle("show", max > 60 && box.scrollTop > 40);
      down.classList.toggle("show", max > 60 && max - box.scrollTop > 40);
    };
    box.addEventListener("scroll", update, { passive: true });
    new MutationObserver(update).observe(box, { childList: true, subtree: true });
    window.addEventListener("resize", update);
    up.addEventListener("click", () => box.scrollTo({ top: 0, behavior: "smooth" }));
    down.addEventListener("click", () => box.scrollTo({ top: box.scrollHeight, behavior: "smooth" }));
    update();
  })();

  // Chat plegable: abierto por defecto (se reinicia en cada visita)
  const tbSection = document.getElementById("view-teambuilder");
  function setChatCollapsed(collapsed) {
    if (!tbSection) return;
    tbSection.classList.toggle("chat-collapsed", collapsed);
    document.querySelectorAll(".chat-toggle-trigger").forEach((b) => b.setAttribute("aria-expanded", String(!collapsed)));
  }
  document.querySelectorAll(".chat-toggle-trigger").forEach((b) => {
    b.addEventListener("click", () => setChatCollapsed(!tbSection.classList.contains("chat-collapsed")));
  });
  setChatCollapsed(false);

  // El analizador reutiliza exactamente las mismas fichas y guía que el creador
  window.PokeUI = {
    async renderCards(team, container, era, formatId) {
      const loc = await loadLocalizedDescriptions(team, era ? era.gen : 9);
      renderTeamGrid(team, loc, container, { era, formatId });
    },
    renderGuide(guide, container, lang) {
      renderStrategyGuide(guide, container, lang);
    },
  };

  document.addEventListener("langchange", async () => {
    renderEmptySlots();
    await rerenderTeam();
    if (lastStrategyGuide) renderStrategyGuide(lastStrategyGuide);
    updateFormatPoolStatus(currentFormatId, false);
  });
});