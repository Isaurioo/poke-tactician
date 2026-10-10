document.addEventListener("DOMContentLoaded", () => {
  const btnRunAnalysis = document.getElementById("btn-run-analysis");
  const showdownInput = document.getElementById("showdown-paste-input");
  const formatIdInput = document.getElementById("analyzer-format-id");
  const emptyState = document.getElementById("analyzer-empty-state");
  const contentState = document.getElementById("analyzer-content");

  if (!btnRunAnalysis) return;

  const TYPE_COLORS = {
    normal: "#94a3b8", fire: "#f97316", water: "#38bdf8", electric: "#eab308",
    grass: "#22c55e", ice: "#06b6d4", fighting: "#dc2626", poison: "#a855f7",
    ground: "#d97706", flying: "#818cf8", psychic: "#ec4899", bug: "#84cc16",
    rock: "#b45309", ghost: "#7c3aed", dragon: "#6366f1", steel: "#64748b",
    dark: "#475569", fairy: "#f472b6"
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

  const KNOWN_SPECIES_TYPES = {
    "charizard": ["Fire", "Flying"],
    "charizardmegay": ["Fire", "Flying"],
    "charizardmegax": ["Fire", "Dragon"],
    "venusaur": ["Grass", "Poison"],
    "venusaurmega": ["Grass", "Poison"],
    "farigiraf": ["Normal", "Psychic"],
    "incineroar": ["Fire", "Dark"],
    "rotomwash": ["Electric", "Water"],
    "garchomp": ["Dragon", "Ground"],
    "garchompmega": ["Dragon", "Ground"],
    "urshifu": ["Fighting", "Dark"],
    "urshifurapidstrike": ["Fighting", "Water"],
    "fluttermane": ["Ghost", "Fairy"],
    "chienpao": ["Dark", "Ice"],
    "tinglu": ["Dark", "Ground"],
    "ironhands": ["Fighting", "Electric"],
    "landorustherian": ["Ground", "Flying"],
    "tornadustherian": ["Flying"],
    "rillaboom": ["Grass"],
    "kingambit": ["Dark", "Steel"],
    "archaludon": ["Steel", "Dragon"],
    "tyranitar": ["Rock", "Dark"]
  };

  function parseShowdownPaste(text) {
    const blocks = text.trim().split(/\n\s*\n/);
    const pokes = [];

    blocks.forEach((block) => {
      const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
      if (lines.length === 0) return;

      const firstLine = lines[0];
      const itemMatch = firstLine.split("@");
      let species = itemMatch[0].trim();
      const item = itemMatch[1] ? itemMatch[1].trim() : "";

      species = species.replace(/\s*\([MF]\)\s*$/, "");
      if (species.includes("(") && species.includes(")")) {
        const m = species.match(/\((.*?)\)/);
        if (m) species = m[1].trim();
      }

      let ability = "";
      let tera = null;
      const moves = [];

      lines.slice(1).forEach((line) => {
        if (line.startsWith("Ability:")) ability = line.replace("Ability:", "").trim();
        else if (line.startsWith("Tera Type:")) tera = line.replace("Tera Type:", "").trim();
        else if (line.startsWith("-")) moves.push(line.replace(/^-+\s*/, "").trim());
      });

      pokes.push({ species, item, ability, tera, moves: moves.slice(0, 4) });
    });

    return pokes;
  }

  function getClientSpeciesTypes(species) {
    const clean = species.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (KNOWN_SPECIES_TYPES[clean]) return KNOWN_SPECIES_TYPES[clean];
    const base = clean.replace(/(mega[xy]?|gmax).*/, "");
    if (KNOWN_SPECIES_TYPES[base]) return KNOWN_SPECIES_TYPES[base];
    return ["Normal"];
  }

  function calculateLocalMatrix(pokes) {
    const allTypes = Object.keys(TYPE_CHART);
    const matrix = {};

    allTypes.forEach((atkType) => {
      const weak = [];
      const resist = [];
      const immune = [];
      const neutral = [];

      pokes.forEach((p) => {
        const types = getClientSpeciesTypes(p.species);
        let mult = 1.0;
        types.forEach((defT) => {
          mult *= (TYPE_CHART[atkType] && TYPE_CHART[atkType][defT] !== undefined) ? TYPE_CHART[atkType][defT] : 1.0;
        });

        const ab = (p.ability || "").toLowerCase();
        if (ab === "levitate" && atkType === "Ground") mult = 0.0;
        else if (ab === "flash fire" && atkType === "Fire") mult = 0.0;
        else if ((ab === "water absorb" || ab === "storm drain") && atkType === "Water") mult = 0.0;
        else if ((ab === "volt absorb" || ab === "lightning rod") && atkType === "Electric") mult = 0.0;
        else if (ab === "sap sipper" && atkType === "Grass") mult = 0.0;

        const entry = { species: p.species, multiplier: mult };
        if (mult >= 2.0) weak.push(entry);
        else if (mult === 0.0) immune.push(entry);
        else if (mult < 1.0) resist.push(entry);
        else neutral.push(entry);
      });

      matrix[atkType] = {
        weak,
        resist,
        immune,
        neutral,
        weak_count: weak.length,
        resist_count: resist.length + immune.length,
      };
    });

    return matrix;
  }

  function formatText(text) {
    if (!text) return "";
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-light">$1</strong>')
      .replace(/^- (.*)$/gm, '<div class="d-flex align-items-start gap-2 mb-2"><i class="bi bi-caret-right-fill text-info mt-1 fs-xs"></i><span>$1</span></div>')
      .replace(/\n/g, "<br>");
  }

  function typeLabel(typeName) {
    const key = String(typeName || "").toLowerCase();
    return window.I18N && I18N.has("type." + key) ? t("type." + key).toUpperCase() : String(typeName || "").toUpperCase();
  }

  function renderTypeBadge(typeName) {
    const bg = TYPE_COLORS[String(typeName).toLowerCase()] || "#64748b";
    return `<span class="badge text-white px-2 py-1" style="background-color:${bg}; font-size:0.65rem; font-weight:700;">${typeLabel(typeName)}</span>`;
  }

  function renderDefensiveMatrix(matrix, pokes) {
    const container = document.getElementById("analyzer-type-matrix-card");
    if (!container) return;

    const effMatrix = (matrix && Object.keys(matrix).length > 0) ? matrix : calculateLocalMatrix(pokes);
    const allTypes = Object.keys(effMatrix);

    const weakSummary = [];
    const resistSummary = [];

    allTypes.forEach((typeKey) => {
      const d = effMatrix[typeKey];
      if (!d) return; // tipos que no existen en esa generación (p. ej. Hada antes de la Gen 6)
      if (d.weak_count >= 2) {
        const affectedPills = d.weak
          .map(
            (w) =>
              `<span class="badge bg-dark border border-secondary-subtle text-light" style="font-size:0.68rem; font-weight:normal;">${w.species} <b class="text-danger">(${w.multiplier}x)</b></span>`
          )
          .join(" ");

        weakSummary.push(`
          <div class="col-12 col-md-6">
            <div class="p-2 bg-body-tertiary rounded border border-danger-subtle d-flex flex-column flex-sm-row align-items-start align-items-sm-center justify-content-between gap-2 h-100">
              <div class="d-flex align-items-center gap-2 flex-shrink-0">
                ${renderTypeBadge(typeKey)}
                <span class="badge bg-danger">${t("an.n_weak", { n: d.weak_count })}</span>
              </div>
              <div class="d-flex flex-wrap gap-1 justify-content-start justify-content-sm-end">
                ${affectedPills}
              </div>
            </div>
          </div>
        `);
      }
      if (d.resist_count >= 3) {
        const resistPills = [...d.resist, ...d.immune]
          .map(
            (r) =>
              `<span class="badge bg-dark border border-secondary-subtle text-light" style="font-size:0.68rem; font-weight:normal;">${r.species} <b class="text-success">(${r.multiplier}x)</b></span>`
          )
          .join(" ");

        resistSummary.push(`
          <div class="col-12 col-md-6">
            <div class="p-2 bg-body-tertiary rounded border border-success-subtle d-flex flex-column flex-sm-row align-items-start align-items-sm-center justify-content-between gap-2 h-100">
              <div class="d-flex align-items-center gap-2 flex-shrink-0">
                ${renderTypeBadge(typeKey)}
                <span class="badge bg-success">${t("an.n_resist", { n: d.resist_count })}</span>
              </div>
              <div class="d-flex flex-wrap gap-1 justify-content-start justify-content-sm-end">
                ${resistPills}
              </div>
            </div>
          </div>
        `);
      }
    });

    // Renderizamos ÚNICAMENTE las dos secciones principales
    container.innerHTML = `
      <div class="row g-2">
        <div class="col-12">
          <span class="text-danger fw-bold small d-block mb-1"><i class="bi bi-exclamation-triangle-fill me-1"></i> ${t("an.weak_title")}</span>
          <div class="row g-2">${weakSummary.join("") || '<div class="col-12 text-secondary small p-2 fst-italic">${t("an.weak_none")}</div>'}</div>
        </div>
        <div class="col-12 mt-2">
          <span class="text-success fw-bold small d-block mb-1"><i class="bi bi-shield-check me-1"></i> ${t("an.resist_title")}</span>
          <div class="row g-2">${resistSummary.join("") || '<div class="col-12 text-secondary small p-2 fst-italic">${t("an.resist_none")}</div>'}</div>
        </div>
      </div>
    `;
  }

  let lastParsed = null;
  let lastMatrix = null;
  let lastAnalysisLang = null;
  let hasAnalysisText = false;

  let lastData = null;
  const esc = (v) => String(v || "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m]));

  function renderRules(d) {
    const box = document.getElementById("analyzer-rules");
    if (!box) return;
    if (!d) { box.innerHTML = ""; return; }
    const list = (items, icon, cls) => items.map((x) => `<li class="mb-1"><i class="bi ${icon} ${cls} me-1"></i>${esc(x)}</li>`).join("");
    let html = "";
    if (d.rules_ok) {
      html += `<div class="alert alert-success py-2 px-3 small mb-2"><i class="bi bi-patch-check-fill me-1"></i><strong>${t("an.rules")}:</strong> ${esc(t("an.rules_ok", { format: d.format_name }))}</div>`;
    } else {
      html += `<div class="alert alert-danger py-2 px-3 small mb-2"><div class="fw-bold mb-1"><i class="bi bi-shield-exclamation me-1"></i>${t("an.rules")} — ${esc(t("an.rules_bad", { n: d.errors.length, format: d.format_name }))}</div><ul class="list-unstyled mb-1">${list(d.errors, "bi-x-circle-fill", "text-danger")}</ul><div class="fst-italic" style="font-size:0.72rem;">${t("an.rules_note")}</div></div>`;
    }
    if (d.warnings && d.warnings.length) {
      html += `<div class="alert alert-warning py-2 px-3 small mb-0"><div class="fw-bold mb-1"><i class="bi bi-lightbulb-fill me-1"></i>${t("an.warns")}</div><ul class="list-unstyled mb-0">${list(d.warnings, "bi-dot", "text-warning")}</ul></div>`;
    }
    box.innerHTML = html;
  }

  function renderSuggestions(d) {
    const box = document.getElementById("analyzer-suggestions");
    const sub = document.getElementById("analyzer-sugg-sub");
    if (!box) return;
    if (sub) sub.textContent = t("an.sugg_sub", { format: d.format_name });
    if (d.suggestions_error) {
      box.innerHTML = `<div class="col-12"><div class="alert alert-warning py-2 small mb-0">${esc(t("an.sugg_err", { error: d.suggestions_error }))}</div></div>`;
      return;
    }
    const META = { fix: ["bi-wrench-adjustable", "#ef4444"], replace: ["bi-arrow-left-right", "#38bdf8"], set: ["bi-sliders", "#eab308"], mega: ["bi-dna", "#a855f7"], note: ["bi-chat-square-text-fill", "#22c55e"] };
    const card = (s) => {
      const [icon, color] = META[s.type] || META.note;
      const title = s.type === "replace" || s.type === "mega" ? `${esc(s.target)} <i class="bi bi-arrow-right mx-1"></i> ${esc(s.add)}` : esc(s.target || "");
      const ch = s.changes || {};
      const rows = [["an.f_item", ch.item], ["an.f_ability", ch.ability], ["an.f_nature", ch.nature], ["an.f_tera", ch.tera_type], ["an.f_moves", (ch.moves || []).join(", ")]]
        .filter(([, v]) => v).map(([k, v]) => `<div class="small"><span class="text-secondary">${t(k)}:</span> <b class="text-light">${esc(v)}</b></div>`).join("");
      const label = s.type === "note" ? "" : `<div class="d-flex align-items-center gap-2 mb-1"><i class="bi ${icon}" style="color:${color}"></i><span class="fw-bold small" style="color:${color}">${t("an.sugg_" + s.type)}</span></div>`;
      return `<div class="card bg-dark p-3" style="border:1px solid ${color}55; border-left:4px solid ${color};">${label}
        ${title ? `<div class="fw-bold text-light mb-1">${title}</div>` : ""}${rows}
        <div class="small text-light-emphasis mt-1">${esc(s.reason)}</div></div>`;
    };
    // Tres secciones siempre visibles; si una no tiene nada que sugerir, se indica que el equipo está bien en ese aspecto
    const COLS = [
      ["replace", ["replace", "mega"], "an.sugg_col_replace", "an.sugg_ok_replace"],
      ["set", ["set", "fix"], "an.sugg_col_set", "an.sugg_ok_set"],
      ["note", ["note"], "an.sugg_col_note", "an.sugg_ok_note"],
    ];
    box.innerHTML = COLS.map(([key, types, titleKey, okKey]) => {
      const [icon, color] = META[key];
      const items = (d.suggestions || []).filter((s) => types.includes(s.type));
      const body = items.length
        ? items.map(card).join("")
        : `<div class="card bg-dark p-3" style="border:1px dashed #22c55e66;"><div class="small text-success"><i class="bi bi-patch-check-fill me-1"></i>${esc(t(okKey, { format: d.format_name }))}</div></div>`;
      return `<div class="col-12 col-lg-4"><div class="d-flex align-items-center gap-2 mb-2"><i class="bi ${icon}" style="color:${color}"></i><span class="fw-bold" style="color:${color}">${t(titleKey)}</span>${items.length ? `<span class="badge rounded-pill" style="background:${color}33;color:${color}">${items.length}</span>` : ""}</div><div class="d-flex flex-column gap-2">${body}</div></div>`;
    }).join("");
  }

  async function renderResult(d) {
    renderRules(d);
    renderSuggestions(d);
    await PokeUI.renderCards(d.team, document.getElementById("analyzer-team-grid"), d.era, d.format_id);
    PokeUI.renderGuide(d.strategy_guide, document.getElementById("analyzer-guide"), d.lang);
  }

  function clearResult() {
    ["analyzer-rules", "analyzer-team-grid", "analyzer-guide", "analyzer-suggestions"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = "";
    });
  }

  const btnPaste = document.getElementById("btn-paste-clipboard");
  if (btnPaste) {
    btnPaste.addEventListener("click", async () => {
      try {
        const txt = await navigator.clipboard.readText();
        if (!txt.trim()) { alert(t("an.paste_empty")); return; }
        showdownInput.value = txt;
      } catch (e) {
        alert(t("an.paste_denied"));
      }
      showdownInput.focus();
    });
  }

  function updateLangNote() {
    const note = document.getElementById("analyzer-lang-note");
    if (!note) return;
    const stale = hasAnalysisText && lastAnalysisLang && lastAnalysisLang !== I18N.lang;
    note.classList.toggle("d-none", !stale);
    if (stale) note.innerHTML = `<i class="bi bi-translate me-1"></i>${t("an.lang_note", { lang: I18N.langLabel() })}`;
  }

  btnRunAnalysis.addEventListener("click", async () => {
    const pasteText = showdownInput.value.trim();
    if (pasteText.length < 15) {
      alert(t("an.invalid"));
      return;
    }

    const selectedFormatId = formatIdInput ? formatIdInput.value : "gen9championsvgc2026regmc";
    const parsedPokemon = parseShowdownPaste(pasteText);
    lastParsed = parsedPokemon;
    lastMatrix = null;
    lastData = null;

    clearResult();
    renderDefensiveMatrix(null, parsedPokemon);
    emptyState.classList.add("d-none");
    contentState.classList.remove("d-none");

    btnRunAnalysis.disabled = true;
    btnRunAnalysis.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> ${t("an.running")}`;

    try {
      const requestLang = I18N.lang;
      const data = await ApiService.analyzeTeam(selectedFormatId, pasteText);
      lastData = data;

      if (data.defensive_matrix && Object.keys(data.defensive_matrix).length) {
        lastMatrix = data.defensive_matrix;
        renderDefensiveMatrix(data.defensive_matrix, parsedPokemon);
      }
      await renderResult(data);
      const resultsCard = document.getElementById("analyzer-results-card");
      if (resultsCard) resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
      hasAnalysisText = true;
      lastAnalysisLang = requestLang;
      updateLangNote();
    } catch (err) {
      alert(t("common.error", { msg: err.message }));
    } finally {
      btnRunAnalysis.disabled = false;
      btnRunAnalysis.innerHTML = `<i class="bi bi-lightning-charge-fill me-1"></i> <span>${t("an.run")}</span>`;
    }
  });

  // Iconos 2D de objetos (el Creador también los carga; aquí se asegura que existan)
  (async function loadIcons() {
    if (!Sprites.hasItemIcons()) {
      Sprites.setItemMap(await ApiService.getItemIcons());
    }
  })();

  document.addEventListener("langchange", () => {
    if (lastParsed) renderDefensiveMatrix(lastMatrix, lastParsed);
    if (lastData) renderResult(lastData);
    updateLangNote();
  });
});
