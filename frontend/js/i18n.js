/* ==========================================================================
   i18n — Español / English / Français
   - Cada clave tiene tres textos: [es, en, fr].
   - HTML estático: data-i18n="clave" | data-i18n-html | data-i18n-placeholder | data-i18n-title
   - JS dinámico: t("clave", { var: valor })
   - Al cambiar de idioma se dispara el evento "langchange" para que cada vista se redibuje.
   NOTA: traduce la INTERFAZ. Los nombres de Pokémon, movimientos, objetos y habilidades
   se mantienen en inglés (nombres oficiales de Showdown). Las descripciones de habilidades
   existen en español e inglés; las de movimientos y objetos solo en inglés.
   ========================================================================== */
(function () {
  const LS_KEY = "pk-lang";
  const LANGS = [
    { code: "es", label: "Español" },
    { code: "en", label: "English" },
    { code: "fr", label: "Français" }
  ];
  const IDX = { es: 0, en: 1, fr: 2 };

  /* clave: [es, en, fr] */
  const T = {
    /* ---------- General ---------- */
    "app.title": ["PokeTactician AI - Suite Competitiva", "PokeTactician AI - Competitive Suite", "PokeTactician AI - Suite compétitive"],
    "nav.builder": ["Creador", "Builder", "Créateur"],
    "nav.analyzer": ["Analizador Showdown", "Showdown Analyzer", "Analyseur Showdown"],
    "nav.dex": ["Pokédex & Compendio", "Pokédex & Compendium", "Pokédex & Compendium"],
    "lang.label": ["Idioma", "Language", "Langue"],
    "common.error": ["Error: {msg}", "Error: {msg}", "Erreur : {msg}"],
    "common.none": ["Ninguno", "None", "Aucun"],
    "common.back": ["Volver a la ficha anterior", "Back to the previous entry", "Retour à la fiche précédente"],
    "common.close": ["Cerrar", "Close", "Fermer"],
    "tech.en": ["Efecto técnico (EN):", "Technical effect:", "Effet technique (EN) :"],
    "ab.fallback_es": ["Descripción solo disponible en español.", "Description only available in Spanish.", "Description disponible uniquement en espagnol."],
    "ab.name_local": ["Nombre ({lang})", "Name ({lang})", "Nom ({lang})"],
    "cp.miss_i18n": ["nombres y descripciones traducidos al español y francés", "translated names and descriptions (Spanish and French)", "noms et descriptions traduits (espagnol et français)"],
    "ev.role_sweeper": ["Sweeper", "Sweeper", "Sweeper"],
    "ev.role_wallbreaker": ["Wallbreaker", "Wallbreaker", "Wallbreaker"],
    "ev.role_tr_attacker": ["Atacante de Trick Room", "Trick Room attacker", "Attaquant Trick Room"],
    "ev.role_support": ["Soporte / pivote", "Support / pivot", "Soutien / pivot"],
    "ev.role_tank": ["Tanque", "Tank", "Tank"],
    "ev.role_balanced": ["Equilibrado", "Balanced", "Équilibré"],
    "ev.speed_tier": ["Velocidad: supera base {n} (neutro, máx.)", "Speed: outspeeds base {n} (neutral, max)", "Vitesse : dépasse base {n} (neutre, max)"],
    "ev.speed_scarf": ["Con Scarf supera base {n} (neutro, máx.)", "With Scarf outspeeds base {n} (neutral, max)", "Avec Scarf dépasse base {n} (neutre, max)"],
    "ev.speed_tailwind": ["Velocidad mínima: depende del Tailwind aliado", "Minimal Speed: relies on allied Tailwind", "Vitesse minimale : dépend du Tailwind allié"],
    "ev.speed_weather": ["Velocidad mínima: depende del clima (×2)", "Minimal Speed: relies on weather (×2)", "Vitesse minimale : dépend de la météo (×2)"],
    "ev.speed_none": ["Sin inversión en Velocidad", "No Speed investment", "Aucun investissement en Vitesse"],
    "ev.custom": ["EVs ajustados a tu pedido", "EVs adjusted to your request", "EVs ajustés à ta demande"],
    "ev.usage": ["EVs del spread más usado (estadísticas reales)", "EVs from the most used spread (real usage stats)", "EVs du spread le plus utilisé (stats réelles)"],
    "strat.sec_core": ["Estilo & Sinergia del Core", "Style & Core Synergy", "Style & synergie du core"],
    "strat.sec_leads": ["Plan de Apertura / Leads", "Opening Plan / Leads", "Plan d'ouverture / Leads"],
    "strat.sec_win": ["Condición de Victoria", "Win Condition", "Condition de victoire"],
    "strat.sec_threats": ["Cobertura de Amenazas Clave", "Key Threat Coverage", "Couverture des menaces clés"],
    "card.stats_classic": ["Stats a Nv. 100 con DVs y Stat Exp máximos (sin EVs modernos)", "Lv. 100 stats with max DVs and Stat Exp (no modern EVs)", "Stats au N. 100 avec DV et Stat Exp max (sans EV modernes)"],
    "card.stats_lv100": ["Nv. 100 (máx.)", "Lv. 100 (max)", "N. 100 (max)"],
    "tb.inspect_hint": ["Pulsa un ataque para ver su efecto", "Tap a move to see its effect", "Touche une attaque pour voir son effet"],
    "tb.guide_error": ["No se pudo generar la guía táctica: {msg}", "The tactical guide could not be generated: {msg}", "Impossible de générer le guide tactique : {msg}"],
    "nat.neutral": ["Neutral (no modifica stats)", "Neutral (no stat changes)", "Neutre (ne modifie pas les stats)"],
    "nat.effect": ["Sube {plus} y baja {minus}", "Raises {plus} and lowers {minus}", "Augmente {plus} et baisse {minus}"],
    "tb.lang_note": ["El texto de la guía se generó en otro idioma. Genera el equipo de nuevo para obtenerlo en {lang}.", "The guide text was generated in another language. Generate the team again to get it in {lang}.", "Le texte du guide a été généré dans une autre langue. Génère à nouveau l'équipe pour l'obtenir en {lang}."],

    /* ---------- Creador de equipos ---------- */
    "tb.format_settings": ["Ajustes de Formato", "Format Settings", "Réglages du format"],
    "tb.format_label": ["Formato Competitivo", "Competitive Format", "Format compétitif"],
    "tb.detecting": ["Detectando mecánicas...", "Detecting mechanics...", "Détection des mécaniques..."],
    "tb.loading": ["Cargando...", "Loading...", "Chargement..."],
    "tb.greeting": ["¡Hola! Configura el formato arriba y dime qué equipo necesitas armar.", "Hi! Set the format above and tell me what team you need to build.", "Salut ! Choisis le format ci-dessus et dis-moi quelle équipe construire."],
    "tb.input_ph": ["Escribe tu estrategia...", "Type your strategy...", "Écris ta stratégie..."],
    "tb.send": ["Enviar", "Send", "Envoyer"],
    "tb.team_title": ["Equipo Táctico (6 Slots)", "Tactical Team (6 Slots)", "Équipe tactique (6 slots)"],
    "tb.team_sub": ["Generación verificada con sets legales oficiales y cálculo Nivel 50", "Generated from verified legal sets with Level 50 calculations", "Génération basée sur des sets légaux vérifiés, calcul niveau 50"],
    "tb.copy": ["Copiar a Showdown", "Copy to Showdown", "Copier vers Showdown"],
    "tb.copied": ["¡Copiado!", "Copied!", "Copié !"],
    "tb.copy_first": ["Primero genera un equipo para copiarlo a Pokémon Showdown.", "Generate a team first to copy it to Pokémon Showdown.", "Génère d'abord une équipe pour la copier vers Pokémon Showdown."],
    "tb.slot": ["Slot {n}", "Slot {n}", "Slot {n}"],
    "tb.guide_title": ["Guía Táctica & Plan de Partida", "Tactical Guide & Game Plan", "Guide tactique & plan de partie"],
    "tb.guide_empty": ["Genera un equipo para visualizar el plan de juego.", "Generate a team to see the game plan.", "Génère une équipe pour afficher le plan de jeu."],
    "tb.thinking": ["Analizando metagame y ensamblando equipo...", "Analyzing the metagame and assembling the team...", "Analyse du métajeu et assemblage de l'équipe..."],
    "tb.done": ["¡Equipo generado para <b>{format}</b>!", "Team generated for <b>{format}</b>!", "Équipe générée pour <b>{format}</b> !"],
    "tb.pool": ["Pool: <b>{pk}</b> Pokémon | <b>{it}</b> Ítems", "Pool: <b>{pk}</b> Pokémon | <b>{it}</b> Items", "Pool : <b>{pk}</b> Pokémon | <b>{it}</b> objets"],
    "tb.badge_megas": ["Megas: Máx {n}", "Megas: Max {n}", "Méga : max {n}"],
    "tb.badge_z": ["Movimientos Z: Activos", "Z-Moves: Active", "Capacités Z : actives"],
    "tb.badge_dmax": ["Dynamax: Permitido", "Dynamax: Allowed", "Dynamax : autorisé"],
    "tb.badge_tera_on": ["Teracristal: Activo", "Terastal: Active", "Téracristal : actif"],
    "tb.badge_tera_off": ["Tera: Prohibido", "Tera: Banned", "Téra : interdit"],
    "tb.badge_classic": ["Combate Clásico (Sin Gimmicks)", "Classic Battle (No Gimmicks)", "Combat classique (sans gimmick)"],
    "tb.badge_restricted": ["Restringidos: {n}", "Restricted: {n}", "Restreints : {n}"],
    "tb.max_n": ["Máx {n}", "Max {n}", "Max {n}"],
    "tb.fmt_updated": ["Formato actualizado a: <b>{name}</b>.", "Format updated to: <b>{name}</b>.", "Format mis à jour : <b>{name}</b>."],
    "tb.fmt_available": ["• Disponibles: {pk} Pokémon y {it} objetos legales.", "• Available: {pk} Pokémon and {it} legal items.", "• Disponibles : {pk} Pokémon et {it} objets légaux."],
    "tb.fmt_params": ["• Parámetros: Megas {megas} | Teracristal {tera}.", "• Parameters: Megas {megas} | Terastal {tera}.", "• Paramètres : Méga {megas} | Téracristal {tera}."],
    "tb.megas_on": ["Activas", "Active", "Activées"],
    "tb.megas_off": ["Prohibidas", "Banned", "Interdites"],
    "tb.tera_on": ["Activo", "Active", "Actif"],
    "tb.tera_off": ["Prohibido", "Banned", "Interdit"],

    /* ---------- Tarjetas del equipo ---------- */
    "card.tab_set": ["Set", "Set", "Set"],
    "card.tab_effects": ["Efectos", "Effects", "Effets"],
    "card.tab_stats": ["Stats", "Stats", "Stats"],
    "card.tab_types": ["Tipos", "Types", "Types"],
    "card.item": ["Ítem", "Item", "Objet"],
    "card.ability": ["Habilidad", "Ability", "Talent"],
    "card.nature": ["Naturaleza", "Nature", "Nature"],
    "card.click_hint": ["(Clic en ítem o ataque)", "(Click an item or move)", "(Clique sur un objet ou une attaque)"],
    "card.role_default": ["Competitivo", "Competitive", "Compétitif"],
    "card.zcrystal": ["CRISTAL Z", "Z-CRYSTAL", "CRISTAL Z"],
    "card.tera": ["TERA: {type}", "TERA: {type}", "TÉRA : {type}"],
    "card.stat_col": ["Stat / Base", "Stat / Base", "Stat / Base"],
    "card.evs_lv50": ["EVs / Nv. 50", "EVs / Lv. 50", "EVs / N. 50"],
    "card.nat_short": ["Nat", "Nat", "Nat"],
    "card.no_item": ["Sin objeto", "No item", "Sans objet"],
    "card.unknown_ability": ["Desconocida", "Unknown", "Inconnu"],
    "card.no_moves": ["Sin movimientos", "No moves", "Aucune attaque"],
    "card.item_fallback": ["Objeto competitivo equipado.", "Held competitive item.", "Objet compétitif porté."],
    "card.ability_fallback": ["Habilidad pasiva del Pokémon.", "The Pokémon's ability.", "Talent du Pokémon."],
    "card.nature_fallback": ["Naturaleza competitiva.", "Competitive nature.", "Nature compétitive."],
    "card.move_fallback": ["Ataque del set.", "Move from the set.", "Attaque du set."],
    "match.x4": ["Superdébil a:", "Very weak to:", "Très faible à :"],
    "match.x2": ["Débil a:", "Weak to:", "Faible à :"],
    "match.x1": ["Daño normal:", "Normal damage:", "Dégâts normaux :"],
    "match.x05": ["Resistente a:", "Resists:", "Résiste à :"],
    "match.x025": ["Superresistente a:", "Strongly resists:", "Très résistant à :"],
    "match.x0": ["Inmune a:", "Immune to:", "Immunisé contre :"],
    "move.pow": ["Pot", "Pow", "Puiss"],
    "move.acc": ["Prec", "Acc", "Préc"],
    "move.prio": ["Prio", "Prio", "Prio"],
    "strat.style": ["Estilo de Juego:", "Playstyle:", "Style de jeu :"],
    "strat.core": ["Sinergia del Core:", "Core Synergy:", "Synergie du core :"],
    "strat.plan": ["Plan de Apertura (Turno a Turno):", "Opening Plan (Turn by Turn):", "Plan d'ouverture (tour par tour) :"],
    "strat.threats": ["Amenazas Cubiertas:", "Threats Covered:", "Menaces couvertes :"],

    /* ---------- Analizador ---------- */
    "an.title": ["Analizador de Equipos de Pokémon Showdown", "Pokémon Showdown Team Analyzer", "Analyseur d'équipes Pokémon Showdown"],
    "an.sub": ["Pega el export de tu equipo para recibir un diagnóstico táctico con IA.", "Paste your team export to get an AI tactical diagnosis.", "Colle l'export de ton équipe pour obtenir un diagnostic tactique par IA."],
    "an.format": ["Formato de Combate:", "Battle Format:", "Format de combat :"],
    "an.export": ["Export de Showdown:", "Showdown Export:", "Export Showdown :"],
    "an.paste_ph": ["Pega aquí tu equipo de Pokémon Showdown...", "Paste your Pokémon Showdown team here...", "Colle ici ton équipe Pokémon Showdown..."],
    "an.run": ["Analizar Equipo con IA", "Analyze Team with AI", "Analyser l'équipe avec l'IA"],
    "an.running": ["Diagnosticando con IA...", "Diagnosing with AI...", "Diagnostic par l'IA..."],
    "an.empty": ["Pega tu equipo de Pokémon Showdown arriba para iniciar el diagnóstico.", "Paste your Pokémon Showdown team above to start the diagnosis.", "Colle ton équipe Pokémon Showdown ci-dessus pour lancer le diagnostic."],
    "an.detected": ["Alineación Detectada", "Detected Lineup", "Équipe détectée"],
    "an.balance": ["Balance de Tipos y Resistencias del Equipo", "Team Type & Resistance Balance", "Équilibre des types et résistances de l'équipe"],
    "an.balance_sub": ["Efectividad defensiva combinada", "Combined defensive effectiveness", "Efficacité défensive combinée"],
    "an.pilot": ["¿Cómo pilotar este equipo?", "How to pilot this team?", "Comment piloter cette équipe ?"],
    "an.threats": ["Amenazas Críticas del Meta", "Critical Meta Threats", "Menaces critiques du méta"],
    "an.recs": ["Sugerencias de Optimización", "Optimization Suggestions", "Suggestions d'optimisation"],
    "an.rules": ["Revisión de Reglas del Formato", "Format Rules Check", "Vérification des règles du format"],
    "an.rules_ok": ["El equipo cumple todas las reglas de {format}.", "The team follows all the rules of {format}.", "L'équipe respecte toutes les règles de {format}."],
    "an.rules_bad": ["{n} infracción(es) en {format}", "{n} rule violation(s) in {format}", "{n} infraction(s) dans {format}"],
    "an.rules_note": ["La guía táctica analiza el equipo tal como está, con sus infracciones.", "The tactical guide analyzes the team as it is, including its violations.", "Le guide tactique analyse l'équipe telle quelle, infractions comprises."],
    "an.warns": ["Recomendaciones", "Recommendations", "Recommandations"],
    "an.guide": ["Guía Táctica del Equipo", "Team Tactical Guide", "Guide tactique de l'équipe"],
    "an.paste": ["Pegar", "Paste", "Coller"],
    "an.paste_empty": ["El portapapeles está vacío.", "The clipboard is empty.", "Le presse-papiers est vide."],
    "an.paste_denied": ["No se pudo leer el portapapeles (permiso denegado o navegador no compatible). Pega con Ctrl+V en el cuadro.", "Couldn't read the clipboard (permission denied or unsupported browser). Paste with Ctrl+V in the box.", "Impossible de lire le presse-papiers (permission refusée ou navigateur non compatible). Colle avec Ctrl+V dans la zone."],
    "tb.chat_hide": ["Ocultar chat", "Hide chat", "Masquer le chat"],
    "tb.chat_show": ["Mostrar chat", "Show chat", "Afficher le chat"],
    "an.input_title": ["Equipo a analizar", "Team to analyze", "Équipe à analyser"],
    "an.input_hint": ["Mostrar / ocultar", "Show / hide", "Afficher / masquer"],
    "an.invalid": ["Pega un set válido exportado de Pokémon Showdown.", "Paste a valid set exported from Pokémon Showdown.", "Colle un set valide exporté depuis Pokémon Showdown."],
    "an.weak_title": ["Vulnerabilidades Principales del Equipo (2+ débiles):", "Main Team Vulnerabilities (2+ weak):", "Principales vulnérabilités de l'équipe (2+ faibles) :"],
    "an.weak_none": ["El equipo no acumula debilidades dobles a ningún tipo elemental.", "The team has no stacked weaknesses to any single type.", "L'équipe ne cumule de faiblesse double à aucun type."],
    "an.resist_title": ["Principales Muros y Resistencias (3+ resistencias/inmunidades):", "Main Walls & Resistances (3+ resistances/immunities):", "Principaux murs et résistances (3+ résistances/immunités) :"],
    "an.resist_none": ["Resistencias bien distribuidas en la alineación.", "Resistances are well distributed across the lineup.", "Résistances bien réparties dans l'équipe."],
    "an.n_weak": ["{n} Débiles", "{n} Weak", "{n} Faibles"],
    "an.n_resist": ["{n} Resistencias", "{n} Resists", "{n} Résistances"],
    "an.lang_note": ["El texto del diagnóstico se generó en otro idioma. Vuelve a analizar el equipo para obtenerlo en {lang}.", "The diagnosis text was generated in another language. Analyze the team again to get it in {lang}.", "Le texte du diagnostic a été généré dans une autre langue. Relance l'analyse pour l'obtenir en {lang}."],
    "fm.title": ["Seleccionar Formato Oficial", "Select Official Format", "Choisir un format officiel"],
    "fm.search": ["Buscar formato...", "Search format...", "Rechercher un format..."],

    /* ---------- Tipos, categorías, stats ---------- */
    "type.normal": ["Normal", "Normal", "Normal"], "type.fire": ["Fuego", "Fire", "Feu"], "type.water": ["Agua", "Water", "Eau"],
    "type.electric": ["Eléctrico", "Electric", "Électrik"], "type.grass": ["Planta", "Grass", "Plante"], "type.ice": ["Hielo", "Ice", "Glace"],
    "type.fighting": ["Lucha", "Fighting", "Combat"], "type.poison": ["Veneno", "Poison", "Poison"], "type.ground": ["Tierra", "Ground", "Sol"],
    "type.flying": ["Volador", "Flying", "Vol"], "type.psychic": ["Psíquico", "Psychic", "Psy"], "type.bug": ["Bicho", "Bug", "Insecte"],
    "type.rock": ["Roca", "Rock", "Roche"], "type.ghost": ["Fantasma", "Ghost", "Spectre"], "type.dragon": ["Dragón", "Dragon", "Dragon"],
    "type.dark": ["Siniestro", "Dark", "Ténèbres"], "type.steel": ["Acero", "Steel", "Acier"], "type.fairy": ["Hada", "Fairy", "Fée"],
    "type.stellar": ["Astral", "Stellar", "Stellaire"],
    "cat.Physical": ["Físico", "Physical", "Physique"], "cat.Special": ["Especial", "Special", "Spécial"], "cat.Status": ["Estado", "Status", "Statut"],
    "stat.hp": ["PS", "HP", "PV"], "stat.atk": ["Ataque", "Attack", "Attaque"], "stat.def": ["Defensa", "Defense", "Défense"],
    "stat.spa": ["At. Esp", "Sp. Atk", "Atq. Spé"], "stat.spd": ["Def. Esp", "Sp. Def", "Déf. Spé"], "stat.spe": ["Veloc.", "Speed", "Vitesse"],
    "ss.hp": ["PS", "HP", "PV"], "ss.atk": ["Atq", "Atk", "Atq"], "ss.def": ["Def", "Def", "Déf"],
    "ss.spa": ["AtqE", "SpA", "AtS"], "ss.spd": ["DefE", "SpD", "DéS"], "ss.spe": ["Vel", "Spe", "Vit"],
    "bs.accuracy": ["Precisión", "Accuracy", "Précision"], "bs.evasion": ["Evasión", "Evasion", "Esquive"],
    "st.brn": ["Quemadura", "Burn", "Brûlure"], "st.par": ["Parálisis", "Paralysis", "Paralysie"], "st.slp": ["Sueño", "Sleep", "Sommeil"],
    "st.frz": ["Congelación", "Freeze", "Gel"], "st.psn": ["Envenenamiento", "Poison", "Empoisonnement"], "st.tox": ["Envenenamiento grave", "Bad poison", "Empoisonnement grave"],

    /* ---------- Compendio: pantalla principal ---------- */
    "cp.title": ["Compendio Competitivo", "Competitive Compendium", "Compendium compétitif"],
    "cp.sub": ["Fichas completas de Pokémon, movimientos, objetos y habilidades. Haz clic en cualquier elemento para ver toda su información.", "Full entries for Pokémon, moves, items and abilities. Click anything to see all of its information.", "Fiches complètes des Pokémon, attaques, objets et talents. Clique sur un élément pour voir toutes ses informations."],
    "cp.search_ph": ["Buscar por nombre o descripción...", "Search by name or description...", "Rechercher par nom ou description..."],
    "cp.tab_pokemon": ["Pokémon", "Pokémon", "Pokémon"], "cp.tab_items": ["Objetos", "Items", "Objets"],
    "cp.tab_abilities": ["Habilidades", "Abilities", "Talents"], "cp.tab_moves": ["Movimientos", "Moves", "Attaques"],
    "cp.loading": ["Cargando base de datos...", "Loading database...", "Chargement de la base de données..."],
    "cp.showing": ["Mostrando {n} de {total} {what}", "Showing {n} of {total} {what}", "{n} sur {total} {what}"],
    "cp.what_pokemon": ["Pokémon", "Pokémon", "Pokémon"], "cp.what_items": ["objetos", "items", "objets"],
    "cp.what_abilities": ["habilidades", "abilities", "talents"], "cp.what_moves": ["movimientos", "moves", "attaques"],
    "cp.no_results": ["No se encontraron resultados para los filtros aplicados.", "No results for the applied filters.", "Aucun résultat pour les filtres appliqués."],
    "cp.error_conn": ["No se pudo conectar con la base de datos local.", "Could not connect to the local database.", "Impossible de se connecter à la base de données locale."],
    "cp.notice": ["Hay información que aún no está en tu base de datos local: <b>{list}</b>. Ejecuta <code>python build_db_extended.py</code> y reinicia el servidor para completarla.", "Some information is not in your local database yet: <b>{list}</b>. Run <code>python build_db_extended.py</code> and restart the server to complete it.", "Certaines informations ne sont pas encore dans ta base locale : <b>{list}</b>. Lance <code>python build_db_extended.py</code> et redémarre le serveur pour les compléter."],
    "cp.miss_learn": ["cómo se aprende cada movimiento (nivel, MT, huevo…)", "how each move is learned (level, TM, egg…)", "comment chaque attaque est apprise (niveau, CT, œuf…)"],
    "cp.miss_moves": ["PP, objetivo, flags y efectos secundarios de los movimientos", "PP, target, flags and secondary effects of moves", "PP, cible, flags et effets secondaires des attaques"],
    "cp.miss_extra": ["altura, peso, grupos huevo, género y evoluciones", "height, weight, egg groups, gender and evolutions", "taille, poids, groupes d'œufs, genre et évolutions"],
    "cp.miss_desc": ["descripciones largas de movimientos, objetos y habilidades", "long descriptions of moves, items and abilities", "descriptions longues des attaques, objets et talents"],
    "cp.miss_icons": ["iconos 2D de los objetos", "2D item icons", "icônes 2D des objets"],

    /* ---------- Filtros y orden ---------- */
    "f.all_types": ["Todos los tipos", "All types", "Tous les types"],
    "f.tier_cat": ["Tier / categoría", "Tier / category", "Tier / catégorie"],
    "f.tier_group": ["Tier (Singles)", "Tier (Singles)", "Tier (Simples)"],
    "f.cat_group": ["Categoría", "Category", "Catégorie"],
    "tier.Illegal": ["Fuera de tiers", "Outside tiers", "Hors tiers"], "tier.Unspecified": ["Sin tier", "No tier", "Sans tier"],
    "tier.NFE": ["NFE", "NFE", "NFE"], "tier.LC": ["LC", "LC", "LC"],
    "pcat.mega": ["Megaevoluciones", "Mega Evolutions", "Méga-évolutions"], "pcat.primal": ["Regresiones primigenias", "Primal Reversions", "Régressions primitives"],
    "pcat.restricted": ["Legendarios restringidos", "Restricted Legendaries", "Légendaires restreints"], "pcat.sublegend": ["Sublegendarios", "Sub-Legendaries", "Sous-légendaires"],
    "pcat.mythical": ["Singulares (míticos)", "Mythicals", "Fabuleux"], "pcat.paradox": ["Paradoja", "Paradox", "Paradoxe"],
    "pcat.base": ["Solo formas base", "Base forms only", "Formes de base uniquement"],
    "f.move_cat_prop": ["Categoría / propiedad", "Category / property", "Catégorie / propriété"],
    "tier.none": ["Sin tier", "No tier", "Sans tier"],
    "f.property_adv": ["Interacciones avanzadas", "Advanced interactions", "Interactions avancées"],
    "fl.minimize": ["Interacción con Minimize", "Minimize interaction", "Interaction avec Minimize"],
    "chat.top": ["Ir al inicio del chat", "Go to top of chat", "Aller au début du chat"],
    "chat.bottom": ["Ir al último mensaje", "Go to latest message", "Aller au dernier message"],
    "an.sugg": ["Mejoras Sugeridas", "Suggested Improvements", "Améliorations suggérées"],
    "an.sugg_sub": ["Cambios que respetan las reglas de {format}. Son recomendaciones: tu equipo no se modifica.", "Changes that follow the rules of {format}. They are recommendations: your team is not modified.", "Changements conformes aux règles de {format}. Ce sont des recommandations : ton équipe n'est pas modifiée."],
    "an.sugg_fix": ["Corrección legal", "Legal fix", "Correction légale"],
    "an.sugg_col_replace": ["Reemplazos", "Replacements", "Remplacements"],
    "an.sugg_col_set": ["Ajustes de set", "Set tweaks", "Ajustements de set"],
    "an.sugg_col_note": ["Consejos", "Tips", "Conseils"],
    "an.sugg_ok_replace": ["Sin reemplazos que sugerir: tus Pokémon cubren bien los roles y las defensas que pide {format}.", "No replacements to suggest: your Pokémon cover the roles and defenses {format} asks for.", "Aucun remplacement à suggérer : tes Pokémon couvrent bien les rôles et défenses qu'exige {format}."],
    "an.sugg_ok_set": ["Tus sets están bien para {format}: no hay ajustes que sugerir.", "Your sets look good for {format}: no tweaks to suggest.", "Tes sets sont bons pour {format} : aucun ajustement à suggérer."],
    "an.sugg_ok_note": ["Sin consejos adicionales: tu equipo está bien armado para {format}.", "No extra tips: your team is well built for {format}.", "Aucun conseil supplémentaire : ton équipe est bien construite pour {format}."],
    "an.sugg_replace": ["Reemplazo", "Replacement", "Remplacement"],
    "an.sugg_set": ["Ajuste de set", "Set tweak", "Ajustement du set"],
    "an.sugg_mega": ["Megaevolución", "Mega Evolution", "Méga-Évolution"],
    "an.sugg_note": ["Consejo", "Tip", "Conseil"],
    "an.sugg_none": ["No hay mejoras que sugerir para este formato.", "No improvements to suggest for this format.", "Aucune amélioration à suggérer pour ce format."],
    "an.sugg_err": ["No se pudieron generar sugerencias: {error}", "Couldn't generate suggestions: {error}", "Impossible de générer des suggestions : {error}"],
    "an.f_item": ["Objeto", "Item", "Objet"], "an.f_ability": ["Habilidad", "Ability", "Talent"], "an.f_nature": ["Naturaleza", "Nature", "Nature"],
    "an.f_tera": ["Teratipo", "Tera Type", "Type Téra"], "an.f_moves": ["Movimientos", "Moves", "Attaques"],
    "f.others": ["Otros", "Other", "Autres"], "f.property": ["Propiedad", "Property", "Propriété"],
    "f.priority": ["Con prioridad (≠ 0)", "With priority (≠ 0)", "Avec priorité (≠ 0)"],
    "f.available": ["Disponibles hoy (no Past)", "Available now (not Past)", "Disponibles aujourd'hui (hors Past)"],
    "f.past_only": ["Solo Past", "Past only", "Past uniquement"],
    "f.all_cats": ["Todas las categorías", "All categories", "Toutes les catégories"],
    "f.availability": ["Disponibilidad", "Availability", "Disponibilité"],
    "f.nodesc": ["Sin descripción", "No description", "Sans description"],
    "f.use": ["Uso", "Usage", "Utilisation"],
    "f.used": ["Usadas por algún Pokémon", "Used by some Pokémon", "Utilisés par un Pokémon"],
    "f.unused": ["Sin Pokémon asociado", "No associated Pokémon", "Aucun Pokémon associé"],
    "aria.filter1": ["Filtro principal", "Main filter", "Filtre principal"], "aria.filter2": ["Filtro secundario", "Secondary filter", "Filtre secondaire"],
    "aria.sort": ["Ordenar por", "Sort by", "Trier par"],
    "sort.num": ["Nº de Pokédex", "Pokédex no.", "N° du Pokédex"], "sort.name": ["Nombre (A-Z)", "Name (A-Z)", "Nom (A-Z)"],
    "sort.bst": ["BST (mayor)", "BST (highest)", "BST (plus élevé)"], "sort.hp": ["PS (mayor)", "HP (highest)", "PV (plus élevés)"],
    "sort.atk": ["Ataque (mayor)", "Attack (highest)", "Attaque (plus élevée)"], "sort.def": ["Defensa (mayor)", "Defense (highest)", "Défense (plus élevée)"],
    "sort.spa": ["Atq. Esp. (mayor)", "Sp. Atk (highest)", "Atq. Spé (plus élevée)"], "sort.spd": ["Def. Esp. (mayor)", "Sp. Def (highest)", "Déf. Spé (plus élevée)"],
    "sort.spe": ["Velocidad (mayor)", "Speed (highest)", "Vitesse (plus élevée)"], "sort.power": ["Potencia (mayor)", "Power (highest)", "Puissance (plus élevée)"],
    "sort.accuracy": ["Precisión (mayor)", "Accuracy (highest)", "Précision (plus élevée)"], "sort.pp": ["PP (mayor)", "PP (highest)", "PP (plus élevés)"],
    "sort.priority": ["Prioridad (mayor)", "Priority (highest)", "Priorité (plus élevée)"], "sort.learners": ["Más aprendido", "Most learned", "Le plus appris"],
    "sort.category": ["Categoría", "Category", "Catégorie"], "sort.count": ["Más Pokémon", "Most Pokémon", "Plus de Pokémon"],

    /* ---------- Tarjetas del listado ---------- */
    "c.past": ["PAST", "PAST", "PAST"],
    "c.past_title": ["No disponible en la generación actual", "Not available in the current generation", "Indisponible dans la génération actuelle"],
    "c.ab_short": ["Hab", "Abil", "Tal."],
    "tag.mega": ["MEGA", "MEGA", "MÉGA"], "tag.primal": ["PRIMAL", "PRIMAL", "PRIMO"], "tag.restricted": ["RESTRINGIDO", "RESTRICTED", "RESTREINT"],
    "tag.paradox": ["PARADOJA", "PARADOX", "PARADOXE"], "tag.mythical": ["MÍTICO", "MYTHICAL", "FABULEUX"], "tag.sublegend": ["SUBLEG.", "SUB-LEG.", "SOUS-LÉG."],
    "c.pot": ["Pot", "Pow", "Puiss"], "c.prec": ["Prec", "Acc", "Préc"],
    "c.learners_n": ["{n} Pokémon lo aprenden", "{n} Pokémon learn it", "{n} Pokémon l'apprennent"],
    "c.learners_none": ["Sin Pokémon registrados", "No Pokémon recorded", "Aucun Pokémon enregistré"],
    "c.no_desc": ["Sin descripción en la base local.", "No description in the local database.", "Aucune description dans la base locale."],
    "c.n_pokemon": ["{n} Pokémon", "{n} Pokémon", "{n} Pokémon"],

    /* ---------- Categorías de habilidades ---------- */
    "abcat.forme": ["Cambio de forma", "Form change", "Changement de forme"],
    "abcat.weather": ["Clima y terreno", "Weather & terrain", "Météo & terrain"],
    "abcat.type": ["Cambio de tipo", "Type change", "Changement de type"],
    "abcat.entry": ["Al entrar", "On entry", "À l'entrée"],
    "abcat.contact": ["Contacto", "Contact", "Contact"],
    "abcat.items": ["Objetos y bayas", "Items & berries", "Objets & baies"],
    "abcat.status": ["Estados", "Status", "Statuts"],
    "abcat.speed": ["Velocidad", "Speed", "Vitesse"],
    "abcat.defense": ["Defensiva", "Defensive", "Défensif"],
    "abcat.healing": ["Curación", "Healing", "Soin"],
    "abcat.utility": ["Utilidad", "Utility", "Utilité"],
    "abcat.offense": ["Ofensiva", "Offensive", "Offensif"],
    "abcat.stats": ["Stats", "Stats", "Stats"],
    "abcat.passive": ["Pasiva", "Passive", "Passif"],
    "ab.no_data": ["Sin datos", "No data", "Sans données"],
    "ab.no_data_long": ["Esta habilidad no tiene descripción en la base local.", "This ability has no description in the local database.", "Ce talent n'a pas de description dans la base locale."],
    "ab.effect": ["Efecto", "Effect", "Effet"], "ab.data": ["Datos", "Data", "Données"],
    "ab.name_en": ["Nombre (EN)", "Name (EN)", "Nom (EN)"], "ab.name_es": ["Nombre (ES)", "Name (ES)", "Nom (ES)"],
    "ab.category": ["Categoría", "Category", "Catégorie"],
    "ab.count": ["Pokémon que la tienen", "Pokémon with it", "Pokémon qui l'ont"], "ab.hidden_count": ["Como habilidad oculta", "As hidden ability", "En talent caché"],
    "ab.hidden_tag": ["OCULTA", "HIDDEN", "CACHÉ"],
    "ab.pokemon_title": ["Pokémon con esta habilidad ({n})", "Pokémon with this ability ({n})", "Pokémon avec ce talent ({n})"],
    "ab.other_lang": ["Descripción en otro idioma ({lang}):", "Description in another language ({lang}):", "Description dans une autre langue ({lang}) :"],
    "ab.fallback_en": ["Descripción solo disponible en inglés.", "Description only available in English.", "Description disponible uniquement en anglais."],
    "slot.0": ["Habilidad 1", "Ability 1", "Talent 1"], "slot.1": ["Habilidad 2", "Ability 2", "Talent 2"],
    "slot.H": ["Habilidad oculta", "Hidden ability", "Talent caché"], "slot.S": ["Habilidad especial", "Special ability", "Talent spécial"],

    /* ---------- Ficha de Pokémon ---------- */
    "pk.tab_summary": ["Resumen", "Summary", "Résumé"], "pk.tab_moves": ["Movimientos", "Moves", "Attaques"],
    "pk.base_stats": ["Stats base (BST {bst})", "Base stats (BST {bst})", "Stats de base (BST {bst})"],
    "pk.col_base": ["Base", "Base", "Base"],
    "pk.col_lv50": ["Nv. 50<br>mín · máx", "Lv. 50<br>min · max", "N. 50<br>min · max"],
    "pk.col_lv100": ["Nv. 100<br>mín · máx", "Lv. 100<br>min · max", "N. 100<br>min · max"],
    "pk.stat_note": ["Mín: IV 0, EV 0, naturaleza desfavorable. Máx: IV 31, 252 EV, naturaleza favorable.", "Min: 0 IV, 0 EV, hindering nature. Max: 31 IV, 252 EV, beneficial nature.", "Min : IV 0, EV 0, nature défavorable. Max : IV 31, 252 EV, nature favorable."],
    "pk.abilities": ["Habilidades", "Abilities", "Talents"],
    "pk.profile": ["Ficha", "Profile", "Fiche"],
    "pk.base_species": ["Especie base", "Base species", "Espèce de base"], "pk.forme": ["Forma", "Forme", "Forme"],
    "pk.height": ["Altura", "Height", "Taille"], "pk.weight": ["Peso", "Weight", "Poids"],
    "pk.lowkick": ["Potencia de Low Kick / Grass Knot", "Low Kick / Grass Knot power", "Puissance de Balayette / Nœud Herbe"],
    "pk.egg": ["Grupos huevo", "Egg groups", "Groupes d'œufs"], "pk.gender": ["Género", "Gender", "Genre"],
    "pk.gender_n": ["Sin género", "Genderless", "Asexué"], "pk.gender_m": ["Solo macho ♂", "Male only ♂", "Mâle uniquement ♂"],
    "pk.gender_f": ["Solo hembra ♀", "Female only ♀", "Femelle uniquement ♀"], "pk.gender_ratio": ["Proporción de género", "Gender ratio", "Répartition des genres"],
    "pk.color": ["Color", "Color", "Couleur"], "pk.gen": ["Generación", "Generation", "Génération"],
    "pk.req_item": ["Objeto requerido", "Required item", "Objet requis"], "pk.req_items": ["Objetos requeridos", "Required items", "Objets requis"],
    "pk.req_move": ["Movimiento requerido", "Required move", "Attaque requise"], "pk.req_ability": ["Habilidad requerida", "Required ability", "Talent requis"],
    "pk.battle_only": ["Solo en combate desde", "Battle-only from", "En combat uniquement depuis"], "pk.changes_from": ["Cambia desde", "Changes from", "Change depuis"],
    "pk.gmax": ["Gigamax", "Gigantamax", "Gigamax"], "pk.tags": ["Etiquetas", "Tags", "Étiquettes"],
    "pk.tier_singles": ["Tier Singles", "Singles tier", "Tier Simples"], "pk.tier_doubles": ["Tier Dobles", "Doubles tier", "Tier Doubles"],
    "pk.tier_natdex": ["Tier National Dex", "National Dex tier", "Tier National Dex"],
    "pk.doubles_prefix": ["Dobles: ", "Doubles: ", "Doubles : "],
    "pk.defense": ["Tabla defensiva", "Defensive chart", "Table défensive"],
    "pk.defense_note": ["Daño recibido por tipo de ataque, sin contar habilidades ni objetos.", "Damage taken by attack type, not counting abilities or items.", "Dégâts reçus par type d'attaque, hors talents et objets."],
    "pk.evolution": ["Línea evolutiva", "Evolution line", "Lignée évolutive"], "pk.forms": ["Otras formas", "Other forms", "Autres formes"],
    "pk.f_mega": ["Megaevolución", "Mega Evolution", "Méga-évolution"], "pk.f_primal": ["Regresión primigenia", "Primal Reversion", "Régression primitive"],
    "pk.f_restricted": ["Legendario restringido", "Restricted Legendary", "Légendaire restreint"], "pk.f_sublegend": ["Sublegendario", "Sub-Legendary", "Sous-légendaire"],
    "pk.f_mythical": ["Singular", "Mythical", "Fabuleux"], "pk.f_paradox": ["Paradoja", "Paradox", "Paradoxe"],
    "evo.use": ["Usar {item}", "Use {item}", "Utiliser {item}"], "evo.use_generic": ["Usar objeto", "Use item", "Utiliser un objet"],
    "evo.trade": ["Intercambio", "Trade", "Échange"], "evo.trade_item": ["Intercambio con {item}", "Trade holding {item}", "Échange avec {item}"],
    "evo.friendship": ["Felicidad alta", "High friendship", "Bonheur élevé"],
    "evo.level_hold": ["Subir nivel con {item}", "Level up holding {item}", "Monter de niveau avec {item}"],
    "evo.level_move": ["Nivel conociendo {move}", "Level up knowing {move}", "Niveau en connaissant {move}"],
    "evo.special": ["Condición especial", "Special condition", "Condition spéciale"], "evo.level": ["Nv. {n}", "Lv. {n}", "N. {n}"],

    /* ---------- Panel de movimientos del Pokémon ---------- */
    "mv.search_ph": ["Buscar movimiento o efecto...", "Search move or effect...", "Rechercher une attaque ou un effet..."],
    "mv.type": ["Tipo", "Type", "Type"], "mv.cat": ["Categoría", "Category", "Catégorie"],
    "mv.sort_name": ["Orden: nombre", "Sort: name", "Tri : nom"], "mv.sort_power": ["Potencia", "Power", "Puissance"],
    "mv.sort_acc": ["Precisión", "Accuracy", "Précision"], "mv.sort_pp": ["PP", "PP", "PP"], "mv.sort_type": ["Tipo", "Type", "Type"],
    "mv.sort_level": ["Nivel de aprendizaje", "Learn level", "Niveau d'apprentissage"],
    "mv.gen9": ["Solo Gen 9", "Gen 9 only", "Gen 9 uniquement"],
    "mv.count": ["{n} de {total} movimientos", "{n} of {total} moves", "{n} sur {total} attaques"],
    "mv.need_script": ["La forma de aprendizaje (nivel, MT, huevo…) aparecerá al ejecutar <code>build_db_extended.py</code>.", "How each move is learned (level, TM, egg…) will appear after running <code>build_db_extended.py</code>.", "La façon d'apprendre chaque attaque (niveau, CT, œuf…) apparaîtra après avoir lancé <code>build_db_extended.py</code>."],
    "mv.none": ["No hay movimientos con esos filtros.", "No moves match those filters.", "Aucune attaque ne correspond à ces filtres."],
    "mv.th_move": ["Movimiento", "Move", "Attaque"], "mv.th_cat": ["Cat.", "Cat.", "Cat."], "mv.th_pow": ["Pot.", "Pow.", "Puiss."],
    "mv.th_acc": ["Prec.", "Acc.", "Préc."], "mv.th_learn": ["Aprendizaje", "Learned", "Apprentissage"], "mv.th_effect": ["Efecto", "Effect", "Effet"],
    "mv.via": ["vía {name}", "via {name}", "via {name}"],
    "mv.via_title": ["Se hereda de una prevolución", "Inherited from a pre-evolution", "Hérité d'une pré-évolution"],
    "lm.L": ["Nivel", "Level", "Niveau"], "lm.Llv": ["Nv. {n}", "Lv. {n}", "N. {n}"], "lm.M": ["MT/MO", "TM/HM", "CT/CS"],
    "lm.T": ["Tutor", "Tutor", "Tuteur"], "lm.E": ["Huevo", "Egg", "Œuf"], "lm.S": ["Evento", "Event", "Événement"],
    "lm.D": ["Dream World", "Dream World", "Dream World"], "lm.V": ["Transferencia", "Transfer", "Transfert"], "lm.R": ["Recordador", "Move Reminder", "Rappel"],
    "lm.older": ["Gen {n}", "Gen {n}", "Gen {n}"],
    "lm.older_title": ["Solo se aprende en generaciones anteriores", "Only learnable in earlier generations", "Appris uniquement lors des générations précédentes"],

    /* ---------- Ficha de movimiento ---------- */
    "mvs.power": ["POTENCIA", "POWER", "PUISSANCE"], "mvs.accuracy": ["PRECISIÓN", "ACCURACY", "PRÉCISION"], "mvs.pp": ["PP", "PP", "PP"],
    "mvs.priority": ["PRIORIDAD", "PRIORITY", "PRIORITÉ"], "mvs.never_miss": ["Nunca falla", "Never misses", "Ne rate jamais"],
    "mvs.effect": ["Efecto", "Effect", "Effet"], "mvs.data": ["Datos", "Data", "Données"], "mvs.target": ["Objetivo", "Target", "Cible"],
    "mvs.target_need": ["— (requiere datos extendidos)", "— (requires extended data)", "— (nécessite les données étendues)"],
    "mvs.type": ["Tipo", "Type", "Type"], "mvs.category": ["Categoría", "Category", "Catégorie"],
    "mvs.avail": ["Disponibilidad", "Availability", "Disponibilité"],
    "mvs.avail_yes": ["Disponible en la generación actual", "Available in the current generation", "Disponible dans la génération actuelle"],
    "mvs.avail_no": ["No disponible en la generación actual", "Not available in the current generation", "Indisponible dans la génération actuelle"],
    "mvs.learners": ["Pokémon que lo aprenden", "Pokémon that learn it", "Pokémon qui l'apprennent"],
    "mvs.learners_gen9": ["({n} en Gen 9)", "({n} in Gen 9)", "({n} en Gen 9)"],
    "mvs.learners_title": ["Pokémon que lo aprenden ({n})", "Pokémon that learn it ({n})", "Pokémon qui l'apprennent ({n})"],
    "mvs.gen9_only": ["Solo quienes lo aprenden en Gen 9", "Only those learning it in Gen 9", "Uniquement ceux qui l'apprennent en Gen 9"],
    "mvs.flags": ["Propiedades y flags", "Properties & flags", "Propriétés & flags"],
    "mvs.no_notable": ["Sin flags destacadas.", "No notable flags.", "Aucun flag notable."],
    "mvs.other_flags": ["Otras:", "Other:", "Autres :"],
    "mvs.flags_hint": ["Flags (contacto, sonido, etc.) disponibles tras ejecutar <code>build_db_extended.py</code>.", "Flags (contact, sound, etc.) become available after running <code>build_db_extended.py</code>.", "Les flags (contact, son, etc.) seront disponibles après avoir lancé <code>build_db_extended.py</code>."],
    "mvs.details": ["Efectos detallados", "Detailed effects", "Effets détaillés"],
    "chip.filter": ["Filtrar Pokémon...", "Filter Pokémon...", "Filtrer les Pokémon..."],
    "chip.none": ["Ninguno registrado.", "None recorded.", "Aucun enregistré."],
    "tg.normal": ["Un objetivo adyacente", "One adjacent target", "Une cible adjacente"], "tg.any": ["Cualquier objetivo", "Any target", "N'importe quelle cible"],
    "tg.adjacentAlly": ["Un aliado adyacente", "One adjacent ally", "Un allié adjacent"], "tg.adjacentAllyOrSelf": ["Aliado adyacente o el usuario", "Adjacent ally or the user", "Allié adjacent ou l'utilisateur"],
    "tg.adjacentFoe": ["Un rival adyacente", "One adjacent foe", "Un adversaire adjacent"], "tg.allAdjacent": ["Todos los Pokémon adyacentes", "All adjacent Pokémon", "Tous les Pokémon adjacents"],
    "tg.allAdjacentFoes": ["Todos los rivales adyacentes", "All adjacent foes", "Tous les adversaires adjacents"], "tg.allies": ["Todos los aliados", "All allies", "Tous les alliés"],
    "tg.allySide": ["Lado aliado del campo", "Your side of the field", "Votre côté du terrain"], "tg.allyTeam": ["Todo el equipo aliado", "Your whole team", "Toute votre équipe"],
    "tg.foeSide": ["Lado rival del campo", "Foe's side of the field", "Côté adverse du terrain"], "tg.randomNormal": ["Un rival aleatorio", "A random foe", "Un adversaire au hasard"],
    "tg.scripted": ["Último Pokémon que atacó al usuario", "The last Pokémon that hit the user", "Le dernier Pokémon ayant touché l'utilisateur"],
    "tg.self": ["El usuario", "The user", "L'utilisateur"], "tg.all": ["Todo el campo", "The whole field", "Tout le terrain"],
    "fl.contact": ["Contacto", "Contact", "Contact"], "fl.protect": ["Bloqueable por Protección", "Blocked by Protect", "Bloqué par Abri"],
    "fl.mirror": ["Copiable (Mov. Espejo)", "Copyable (Mirror Move)", "Copiable (Mimique)"], "fl.punch": ["Puño", "Punch", "Poing"],
    "fl.bite": ["Mordisco", "Bite", "Morsure"], "fl.bullet": ["Bomba/Balín", "Ball/Bomb", "Balle/Bombe"], "fl.sound": ["Sonido", "Sound", "Son"],
    "fl.powder": ["Polvo", "Powder", "Poudre"], "fl.pulse": ["Pulso", "Pulse", "Pulsation"], "fl.slicing": ["Cortante", "Slicing", "Tranchant"],
    "fl.wind": ["Viento", "Wind", "Vent"], "fl.dance": ["Baile", "Dance", "Danse"], "fl.heal": ["Curación", "Healing", "Soin"],
    "fl.snatch": ["Robable", "Snatchable", "Subtilisable"], "fl.reflectable": ["Reflejable (Espejo Mágico)", "Reflectable (Magic Coat)", "Réfléchissable (Reflet Magik)"],
    "fl.charge": ["Requiere turno de carga", "Needs a charging turn", "Nécessite un tour de charge"], "fl.recharge": ["Requiere recarga", "Needs recharge", "Nécessite une recharge"],
    "fl.gravity": ["Bloqueado por Gravedad", "Blocked by Gravity", "Bloqué par Gravité"], "fl.defrost": ["Descongela al usuario", "Thaws the user", "Dégèle l'utilisateur"],
    "fl.distance": ["Alcanza a distancia", "Reaches from afar", "Atteint à distance"], "fl.bypasssub": ["Ignora Sustituto", "Bypasses Substitute", "Ignore Clone"],
    "fl.nonsky": ["No usable en Sky Battle", "Not usable in Sky Battles", "Inutilisable en Combat aérien"], "fl.allyanim": ["Animación sobre aliado", "Ally animation", "Animation sur allié"],
    "fl.metronome": ["Puede salir con Metrónomo", "Can come out of Metronome", "Peut sortir de Métronome"], "fl.cantusetwice": ["No repetible seguido", "Cannot be used twice in a row", "Non répétable d'affilée"],
    "fl.futuremove": ["Ataque diferido", "Delayed attack", "Attaque différée"], "fl.noassist": ["No usable con Ayuda", "Not usable with Assist", "Inutilisable avec Assistance"],
    "fl.nosleeptalk": ["No usable con Sleep Talk", "Not usable with Sleep Talk", "Inutilisable avec Blabla Dodo"], "fl.failencore": ["Falla con Otra Vez", "Fails with Encore", "Échoue avec Encore"],
    "fl.failcopycat": ["Falla con Copión", "Fails with Copycat", "Échoue avec Copie"], "fl.failinstruct": ["Falla con Orden", "Fails with Instruct", "Échoue avec Ordre"],
    "fl.failmefirst": ["Falla con Yo Primero", "Fails with Me First", "Échoue avec Moi d'Abord"], "fl.failmimic": ["Falla con Mimético", "Fails with Mimic", "Échoue avec Copie-Conforme"],
    "fl.noparentalbond": ["Sin Amor Filial", "No Parental Bond", "Sans Amour Filial"], "fl.nosketch": ["No copiable (Esbozo)", "Not copyable (Sketch)", "Non copiable (Gribouille)"],
    "fl.mustpressure": ["Afectado por Presión", "Affected by Pressure", "Affecté par Pression"], "fl.pledgecombo": ["Combinable (Pledge)", "Combinable (Pledge)", "Combinable (Pledge)"],
    "mp.drain": ["Drenaje", "Drain", "Drain"], "mp.drain_v": ["Recupera {x} del daño infligido", "Recovers {x} of the damage dealt", "Récupère {x} des dégâts infligés"],
    "mp.recoil": ["Retroceso", "Recoil", "Contrecoup"], "mp.recoil_v": ["Sufre {x} del daño infligido", "Takes {x} of the damage dealt", "Subit {x} des dégâts infligés"],
    "mp.recoil_half": ["Pierde la mitad de sus PS máximos", "Loses half of its max HP", "Perd la moitié de ses PV max"],
    "mp.recoil_quarter": ["Pierde 1/4 de sus PS máximos", "Loses 1/4 of its max HP", "Perd 1/4 de ses PV max"],
    "mp.crash": ["Si falla", "If it misses", "En cas d'échec"], "mp.crash_v": ["El usuario recibe daño", "The user takes damage", "L'utilisateur subit des dégâts"],
    "mp.heal": ["Curación", "Healing", "Soin"], "mp.heal_v": ["Restaura {x} de los PS máximos", "Restores {x} of max HP", "Restaure {x} des PV max"],
    "mp.multihit": ["Golpes", "Hits", "Coups"], "mp.multihit_range": ["{a} a {b} golpes", "{a} to {b} hits", "{a} à {b} coups"], "mp.multihit_n": ["{n} golpes", "{n} hits", "{n} coups"],
    "mp.crit": ["Probabilidad de crítico", "Critical hit chance", "Chances de critique"], "mp.crit_v": ["Etapa +{n}", "Stage +{n}", "Palier +{n}"],
    "mp.willcrit": ["Crítico", "Critical hit", "Critique"], "mp.willcrit_v": ["Siempre es golpe crítico", "Always a critical hit", "Toujours un coup critique"],
    "mp.ohko": ["KO", "KO", "K.O."], "mp.ohko_v": ["Debilita de un golpe si acierta", "Knocks out in one hit if it lands", "K.O. en un coup s'il touche"],
    "mp.damage": ["Daño fijo", "Fixed damage", "Dégâts fixes"], "mp.damage_level": ["Igual al nivel del usuario", "Equal to the user's level", "Égal au niveau de l'utilisateur"], "mp.damage_hp": ["{n} PS", "{n} HP", "{n} PV"],
    "mp.switch": ["Cambio", "Switch", "Changement"], "mp.switch_v": ["El usuario se retira tras usarlo", "The user switches out after use", "L'utilisateur est remplacé après usage"],
    "mp.switch_copy": ["(transfiere cambios de stats)", "(passes stat changes)", "(transmet les changements de stats)"],
    "mp.force": ["Cambio forzado", "Forced switch", "Changement forcé"], "mp.force_v": ["Obliga al objetivo a salir", "Forces the target out", "Force la cible à quitter le combat"],
    "mp.boosts_t": ["Cambios de stats (objetivo)", "Stat changes (target)", "Changements de stats (cible)"], "mp.boosts_s": ["Cambios de stats (usuario)", "Stat changes (user)", "Changements de stats (utilisateur)"],
    "mp.self_vol": ["Estado propio", "Self effect", "Effet sur soi"], "mp.status": ["Estado que provoca", "Inflicts", "Statut infligé"],
    "mp.volatile": ["Estado volátil", "Volatile status", "Statut volatil"], "mp.side": ["Condición de lado", "Side condition", "Condition de côté"],
    "mp.slot": ["Condición de posición", "Slot condition", "Condition de position"], "mp.weather": ["Clima", "Weather", "Météo"],
    "mp.terrain": ["Campo", "Terrain", "Terrain"], "mp.pseudo": ["Efecto de campo", "Field effect", "Effet de terrain"],
    "mp.secondary": ["Efecto secundario", "Secondary effect", "Effet secondaire"], "mp.secondaries": ["Efectos secundarios", "Secondary effects", "Effets secondaires"],
    "mp.chance": ["{n}% de probabilidad: ", "{n}% chance: ", "{n} % de chances : "],
    "mp.sec_target": ["modifica al objetivo: {x}", "changes the target: {x}", "modifie la cible : {x}"], "mp.sec_self": ["modifica al usuario: {x}", "changes the user: {x}", "modifie l'utilisateur : {x}"],
    "mp.sec_status": ["provoca {x}", "inflicts {x}", "inflige {x}"], "mp.sec_volatile": ["provoca «{x}»", "causes “{x}”", "provoque « {x} »"],
    "mp.sec_onhit": ["efecto especial al impactar", "special effect on hit", "effet spécial à l'impact"],
    "mp.off_stat": ["Stat ofensivo usado", "Offensive stat used", "Stat offensive utilisée"], "mp.def_stat": ["Stat defensivo usado", "Defensive stat used", "Stat défensive utilisée"],
    "mp.off_poke": ["Atacante para el cálculo", "Attacker used in the calculation", "Attaquant utilisé dans le calcul"], "mp.off_target": ["El objetivo", "The target", "La cible"],
    "mp.ign_def": ["Defensa", "Defense", "Défense"], "mp.ign_def_v": ["Ignora los cambios de stats defensivos del objetivo", "Ignores the target's defensive stat changes", "Ignore les changements de stats défensives de la cible"],
    "mp.ign_eva": ["Evasión", "Evasion", "Esquive"], "mp.ign_eva_v": ["Ignora los cambios de evasión del objetivo", "Ignores the target's evasion changes", "Ignore les changements d'esquive de la cible"],
    "mp.ign_imm": ["Inmunidades", "Immunities", "Immunités"], "mp.ign_imm_v": ["Ignora las inmunidades de tipo", "Ignores type immunities", "Ignore les immunités de type"],
    "mp.ign_ab": ["Habilidad", "Ability", "Talent"], "mp.ign_ab_v": ["Ignora la habilidad del objetivo", "Ignores the target's ability", "Ignore le talent de la cible"],
    "mp.breaks": ["Protección", "Protection", "Protection"], "mp.breaks_v": ["Rompe Protección y similares", "Breaks Protect and similar moves", "Brise Abri et les attaques similaires"],
    "mp.stalling": ["Tipo", "Kind", "Nature"], "mp.stalling_v": ["Movimiento de protección (falla si se repite)", "Protection move (fails if repeated)", "Attaque de protection (échoue si répétée)"],
    "mp.thaws": ["Hielo", "Ice", "Glace"], "mp.thaws_v": ["Descongela al objetivo", "Thaws the target", "Dégèle la cible"],
    "mp.sleep": ["Sueño", "Sleep", "Sommeil"], "mp.sleep_v": ["Usable mientras el usuario duerme", "Usable while the user is asleep", "Utilisable pendant le sommeil"],
    "mp.future": ["Diferido", "Delayed", "Différé"], "mp.future_v": ["Golpea unos turnos después", "Hits a few turns later", "Frappe quelques tours plus tard"],
    "mp.nopp": ["PP", "PP", "PP"], "mp.nopp_v": ["No se puede aumentar con PP Máx", "Cannot be raised with PP Max", "Ne peut pas être augmenté avec PP Max"],
    "mp.zmove": ["Movimiento Z", "Z-Move", "Capacité Z"], "mp.maxmove": ["Movimiento Dinamax", "Max Move", "Attaque Dynamax"], "mp.power_n": ["Potencia {n}", "Power {n}", "Puissance {n}"],
    "mp.contest": ["Concurso", "Contest", "Concours"], "mp.class": ["Clase", "Class", "Classe"],
    "mp.isz_v": ["Movimiento Z exclusivo", "Exclusive Z-Move", "Capacité Z exclusive"], "mp.ismax_v": ["Movimiento Dinamax/Gigamax", "Dynamax/Gigantamax move", "Attaque Dynamax/Gigamax"],

    /* ---------- Ficha de objeto ---------- */
    "it.effect": ["Efecto", "Effect", "Effet"], "it.data": ["Datos", "Data", "Données"],
    "it.fling": ["Lanzamiento (Fling)", "Fling", "Dégagement"], "it.fling_v": ["Potencia {n}", "Power {n}", "Puissance {n}"],
    "it.natgift": ["Don Natural", "Natural Gift", "Don Naturel"], "it.natgift_v": ["Potencia {n} · tipo {t}", "Power {n} · {t} type", "Puissance {n} · type {t}"],
    "it.plate": ["Cambia el tipo de Arceus a", "Changes Arceus's type to", "Change le type d'Arceus en"],
    "it.memory": ["Cambia el tipo de Silvally a", "Changes Silvally's type to", "Change le type de Silvallié en"],
    "it.drive": ["Cambia el tipo de Genesect a", "Changes Genesect's type to", "Change le type de Genesect en"],
    "it.ztype": ["Convierte movimientos tipo", "Converts moves of type", "Convertit les attaques de type"],
    "it.zmove": ["Movimiento Z", "Z-Move", "Capacité Z"], "it.zfrom": ["Requiere el movimiento", "Requires the move", "Nécessite l'attaque"],
    "it.forced": ["Forma que fuerza", "Forced forme", "Forme forcée"], "it.boosts": ["Modifica stats", "Modifies stats", "Modifie les stats"],
    "it.introduced": ["Introducido en", "Introduced in", "Introduit en"], "it.gen_n": ["Generación {n}", "Generation {n}", "Génération {n}"],
    "it.mega_to": ["Megaevoluciona a", "Mega Evolves into", "Méga-évolue en"],
    "it.is_choice": ["Objeto Choice (bloquea el movimiento)", "Choice item (locks the move)", "Objet Choice (verrouille l'attaque)"],
    "it.derived": ["Descripción deducida de los datos de Pokémon.", "Description derived from Pokémon data.", "Description déduite des données Pokémon."],
    "it.no_desc_hint": ["Sin descripción en la base local. Ejecuta <code>build_db_extended.py</code> para descargarla.", "No description in the local database. Run <code>build_db_extended.py</code> to download it.", "Aucune description dans la base locale. Lance <code>build_db_extended.py</code> pour la télécharger."],
    "it.extra_hint": ["Lanzamiento, Don Natural y generación se añaden con <code>build_db_extended.py</code>.", "Fling, Natural Gift and generation are added by <code>build_db_extended.py</code>.", "Dégagement, Don Naturel et génération sont ajoutés par <code>build_db_extended.py</code>."],
    "it.required_by": ["Requerido por ({n})", "Required by ({n})", "Requis par ({n})"], "it.users": ["Uso exclusivo de ({n})", "Exclusive to ({n})", "Exclusif à ({n})"],
    "it.who": ["Quién lo usa", "Who uses it", "Qui l'utilise"],
    "it.general": ["Es un objeto de uso general: cualquier Pokémon puede llevarlo.", "General-purpose item: any Pokémon can hold it.", "Objet à usage général : n'importe quel Pokémon peut le porter."],
    "ic.megastone": ["Megapiedra", "Mega Stone", "Méga-gemme"], "ic.zcrystal": ["Cristal Z", "Z-Crystal", "Cristal Z"], "ic.berry": ["Baya", "Berry", "Baie"],
    "ic.choice": ["Choice", "Choice", "Choice"], "ic.plate": ["Tabla", "Plate", "Plaque"], "ic.memory": ["Memoria", "Memory", "Disque"],
    "ic.drive": ["Módulo", "Drive", "Module"], "ic.gem": ["Gema", "Gem", "Gemme"], "ic.pokeball": ["Poké Ball", "Poké Ball", "Poké Ball"],
    "ic.mask": ["Máscara", "Mask", "Masque"], "ic.seed": ["Semilla", "Seed", "Graine"], "ic.fossil": ["Fósil", "Fossil", "Fossile"],
    "ic.mail": ["Carta", "Mail", "Lettre"], "ic.herb": ["Hierba", "Herb", "Herbe"], "ic.orb": ["Orbe/Cristal", "Orb/Crystal", "Orbe/Cristal"],
    "ic.general": ["General", "General", "Général"]
  };

  const DICT = { es: {}, en: {}, fr: {} };
  Object.keys(T).forEach((k) => {
    DICT.es[k] = T[k][0];
    DICT.en[k] = T[k][1];
    DICT.fr[k] = T[k][2];
  });

  let lang = "es";
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved && DICT[saved]) lang = saved;
  } catch (e) { /* almacenamiento no disponible */ }

  function t(key, vars) {
    let s = DICT[lang][key];
    if (s === undefined) s = DICT.es[key];
    if (s === undefined) return key;
    if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m));
    return s;
  }

  function has(key) {
    return DICT.es[key] !== undefined;
  }

  function apply(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    scope.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
    scope.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder)); });
    scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.setAttribute("title", t(el.dataset.i18nTitle));
      el.setAttribute("aria-label", t(el.dataset.i18nTitle));
    });
    scope.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
  }

  function setLang(code, silent) {
    if (!DICT[code]) return;
    lang = code;
    try { localStorage.setItem(LS_KEY, code); } catch (e) { /* ignorar */ }
    document.documentElement.setAttribute("lang", code);
    document.title = t("app.title");
    apply(document);
    const sel = document.getElementById("lang-select");
    if (sel && sel.value !== code) sel.value = code;
    if (!silent) document.dispatchEvent(new CustomEvent("langchange", { detail: { lang: code } }));
  }

  window.I18N = {
    t, has, apply, setLang, LANGS,
    get lang() { return lang; },
    langLabel(code) { const l = LANGS.find((x) => x.code === (code || lang)); return l ? l.label : code; },
    keys: () => Object.keys(T)
  };
  window.t = t;

  document.addEventListener("DOMContentLoaded", () => {
    const sel = document.getElementById("lang-select");
    if (sel) {
      sel.innerHTML = LANGS.map((l) => `<option value="${l.code}">${l.label}</option>`).join("");
      sel.value = lang;
      sel.addEventListener("change", () => setLang(sel.value));
    }
    setLang(lang, true);
  });
})();
