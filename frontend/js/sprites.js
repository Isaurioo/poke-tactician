/* ==========================================================================
   SPRITES 100% 2D
   - Pokémon: sprites estáticos pixel-art estilo Gen 5 de Showdown (carpeta /gen5/).
     NUNCA se usan las carpetas /ani/ ni /dex/ (renders 3D). Si un Pokémon no tiene sprite
     2D (muy recientes), se prueba su forma base y, por último, una Poké Ball dibujada en SVG.
   - Objetos: icono 2D de la hoja oficial itemicons-sheet.png (24x24 px por icono), usando el
     `spritenum` de cada objeto. Si aún no hay spritenum (no se ejecutó build_db_extended.py)
     se muestra un icono genérico de objeto dibujado en SVG.
   ========================================================================== */
(function () {
  const BASE = "https://play.pokemonshowdown.com/sprites/gen5";
  const ITEM_SHEET = "https://play.pokemonshowdown.com/sprites/itemicons-sheet.png?v1";

  const BALL_SVG = "data:image/svg+xml;utf8," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" fill="#f8fafc" stroke="#1e293b" stroke-width="4"/>' +
    '<path d="M4 32a28 28 0 0 1 56 0z" fill="#ef4444" stroke="#1e293b" stroke-width="4"/>' +
    '<path d="M4 32h56" stroke="#1e293b" stroke-width="4"/><circle cx="32" cy="32" r="8" fill="#f8fafc" stroke="#1e293b" stroke-width="4"/></svg>'
  );
  const ITEM_SVG = "data:image/svg+xml;utf8," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="13" rx="3" fill="#475569" stroke="#0f172a" stroke-width="1.5"/>' +
    '<path d="M8 7V5.5A2.5 2.5 0 0 1 10.5 3h3A2.5 2.5 0 0 1 16 5.5V7" fill="none" stroke="#0f172a" stroke-width="1.5"/>' +
    '<rect x="9" y="11" width="6" height="4" rx="1" fill="#fbbf24" stroke="#0f172a" stroke-width="1"/></svg>'
  );

  let itemMap = {};

  const compact = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const kebab = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9-]/g, "");
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ------------------------------ Pokémon ------------------------------ */
  // p puede ser un string ("Charizard-Mega-X") o un objeto { base_species, forme, name }
  function candidates(p) {
    let base, forme, name;
    if (typeof p === "string") {
      name = p;
      const parts = p.split("-");
      // Ho-Oh, Porygon-Z, Kommo-o... conservan el guion como parte del nombre base
      const keepHyphen = /^(ho-oh|porygon-z|jangmo-o|hakamo-o|kommo-o)/i.exec(p);
      if (keepHyphen) {
        base = keepHyphen[1];
        forme = p.slice(keepHyphen[1].length).replace(/^-/, "");
      } else {
        base = parts[0];
        forme = parts.slice(1).join("");
      }
    } else {
      name = p.name || "";
      base = p.base_species || p.name || "";
      forme = p.forme && p.forme !== "Base" ? p.forme : "";
    }

    const f = compact(forme);
    const suffix = f ? "-" + f : "";
    const list = [
      `${BASE}/${compact(base)}${suffix}.png`,
      `${BASE}/${kebab(base)}${suffix}.png`,
      `${BASE}/${compact(name)}.png`,
      `${BASE}/${kebab(name)}.png`,
      `${BASE}/${compact(base)}.png`,
      `${BASE}/${kebab(base)}.png`
    ];
    return [...new Set(list)].concat([BALL_SVG]);
  }

  function onError(img) {
    try {
      const rest = JSON.parse(img.getAttribute("data-candidates") || "[]");
      if (rest.length) {
        const next = rest.shift();
        img.setAttribute("data-candidates", JSON.stringify(rest));
        img.src = next;
        if (next === BALL_SVG) img.classList.add("pk-sprite-missing");
        return;
      }
    } catch (e) { /* sin más candidatos */ }
    img.onerror = null;
  }

  function pokemon(p, size = 48, extraClass = "") {
    const list = candidates(p);
    const alt = typeof p === "string" ? p : p.name;
    const rest = esc(JSON.stringify(list.slice(1)));
    const crisp = size >= 96 ? "pixelated" : "auto";
    return `<img class="pk-sprite ${extraClass}" src="${list[0]}" alt="${esc(alt)}" loading="lazy" ` +
      `style="width:${size}px;height:${size}px;image-rendering:${crisp};" data-candidates="${rest}" onerror="Sprites.onError(this)">`;
  }

  /* ------------------------------- Objetos ------------------------------ */
  function setItemMap(map) {
    itemMap = map || {};
  }

  function hasItemIcons() {
    return Object.keys(itemMap).length > 0;
  }

  // ref: nombre ("Choice Scarf"), id ("choicescarf") u objeto { id, name, spritenum }
  function item(ref, size = 24) {
    let id = "", name = "", num = null;
    if (ref && typeof ref === "object") {
      id = ref.id || compact(ref.name);
      name = ref.name || id;
      num = ref.spritenum;
    } else {
      name = String(ref || "");
      id = compact(name);
    }
    if (num === null || num === undefined) {
      const mapped = itemMap[id];
      num = mapped === undefined ? null : mapped;
    }

    const scale = size / 24;
    const box = `display:inline-block;flex:none;width:${size}px;height:${size}px;position:relative;vertical-align:middle;`;
    if (num === null) {
      return `<span class="pk-item-icon" style="${box}" title="${esc(name)}"><img src="${ITEM_SVG}" alt="" style="width:100%;height:100%;"></span>`;
    }
    const top = Math.floor(num / 16) * 24;
    const left = (num % 16) * 24;
    return `<span class="pk-item-icon" style="${box}" title="${esc(name)}">` +
      `<span style="position:absolute;left:0;top:0;width:24px;height:24px;transform:scale(${scale});transform-origin:0 0;` +
      `background:transparent url(${ITEM_SHEET}) no-repeat scroll -${left}px -${top}px;image-rendering:pixelated;"></span></span>`;
  }

  window.Sprites = { pokemon, item, candidates, onError, setItemMap, hasItemIcons, BALL_SVG, compact };
  // compatibilidad con el nombre que usaba el compendio
  window.handleSpriteImgError = onError;
})();
