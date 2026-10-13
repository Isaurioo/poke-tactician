const API_BASE = "/api";

const ApiService = {
  async getFormats() {
    const response = await fetch(`${API_BASE}/formats`);
    if (!response.ok) {
      throw new Error(`Error al cargar formatos (${response.status})`);
    }
    return await response.json();
  },

  async getFormatPool(formatId) {
    const cleanId = formatId.toLowerCase().replace(/[^a-z0-9]/g, "");
    const response = await fetch(`${API_BASE}/format-pool/${cleanId}`);
    if (!response.ok) {
      throw new Error(`Error al filtrar el formato ${cleanId}`);
    }
    return await response.json();
  },

  _lang() {
    return (window.I18N && window.I18N.lang) || "es";
  },

  async generateTeam(formatId, prompt) {
    const cleanId = formatId.toLowerCase().replace(/[^a-z0-9]/g, "");
    const response = await fetch(`${API_BASE}/generate-team`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        format_id: cleanId,
        prompt: prompt,
        lang: this._lang(),
      }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Error del servidor (${response.status})`);
    }

    return await response.json();
  },

  async chat(formatId, messages, team) {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        format_id: formatId.toLowerCase().replace(/[^a-z0-9]/g, ""),
        messages: messages,
        team: team || null,
        lang: this._lang(),
      }),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Error del servidor (${response.status})`);
    }
    return await response.json();
  },

  async getCompendium() {
    const response = await fetch(`${API_BASE}/compendium`);
    if (!response.ok) {
      throw new Error(`Error al cargar compendio (${response.status})`);
    }
    return await response.json();
  },

  // Alias para asegurar compatibilidad con todas las vistas
  async getCompendiumOverview() {
    return await this.getCompendium();
  },

  async _getDetail(kind, name) {
    const response = await fetch(`${API_BASE}/compendium/${kind}/${encodeURIComponent(name)}`);
    if (!response.ok) {
      throw new Error(`No se pudo cargar el detalle de ${name} (${response.status})`);
    }
    return await response.json();
  },

  async getPokemonDetail(name) {
    return await this._getDetail("pokemon", name);
  },

  async getMoveDetail(name) {
    return await this._getDetail("move", name);
  },

  async getItemDetail(name) {
    return await this._getDetail("item", name);
  },

  async getAbilityDetail(name) {
    return await this._getDetail("ability", name);
  },

  // {id_objeto: spritenum} -> icono 2D de cada objeto (hoja oficial de Showdown)
  async getItemIcons() {
    try {
      const response = await fetch(`${API_BASE}/compendium/item-icons`);
      return response.ok ? await response.json() : {};
    } catch (e) {
      return {};
    }
  },

  // Nombres y descripciones traducidos (es / fr) del compendio
  async getL10n(lang) {
    try {
      const response = await fetch(`${API_BASE}/compendium/l10n/${encodeURIComponent(lang)}`);
      return response.ok ? await response.json() : null;
    } catch (e) {
      return null;
    }
  },

  // Descripciones (en inglés) de habilidades, objetos y movimientos de un equipo
  async describeTerms(abilities, items, moves) {
    try {
      const response = await fetch(`${API_BASE}/compendium/describe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ abilities, items, moves }),
      });
      return response.ok ? await response.json() : null;
    } catch (e) {
      return null;
    }
  },

  async analyzeTeam(formatId, paste) {
    const response = await fetch(`${API_BASE}/analyze-team`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        format_id: formatId,
        paste: paste,
        lang: this._lang(),
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Error al analizar (${response.status})`);
    }
    return await response.json();
  },
};