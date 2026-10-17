

## Novedades
- **Chat conversacional** (`POST /api/chat`): habla normal, pide un equipo y luego pide cambios ("cambia X por Y", "dale Choice Scarf a Garchomp"). Funciona en español, inglés y francés.
- **Validador final** (`src/core/team_validator.py`): comprueba y corrige reglas del formato (Megas, restringidos, ítems duplicados, bans, movimientos aprendibles, cláusulas de sueño/OHKO/evasión, EVs).
- Correcciones de datos: Megapiedras, Megas Z-A mal marcadas, Pokémon "Illegal"/formas de combate en Gen 9, movimientos heredados de preevoluciones.

- **Equipos de referencia** (`src/services/reference_teams.py` + `web_lookup.py`): campeón de un torneo, jugador, Big 6, "equipo popular/meta", arquetipos con nombre. Orden de fuentes (y `notes` dice cuál se usó): (1) equipo verificado de `src/data/known_teams.json`; (2) **búsqueda web en vivo** con la IA del proveedor (Gemini `google_search` o Groq `compound`; sin clave o sin cuota cae al siguiente), con las fuentes consultadas; (3) respaldo para Big 6/popular: uso real del formato EXACTO (Smogon stats, con Mega si la piedra domina); (4) memoria del modelo, marcada como NO verificada. Todo se valida contra el formato. Variables opcionales: `AI_SEARCH_MODEL`, `WEB_LOOKUP_TIMEOUT`.
- **Sets precisos**: `fetch_live_format_chaos` ahora carga SIEMPRE primero el formato EXACTO (Smogon, últimos 3 meses, y pkmn.github.io) y solo usa formatos de respaldo (marcados con `fallback_from`) si el exacto casi no tiene datos; antes los respaldos (Doubles OU, OU) pisaban al formato exacto. Además los pesos de uso en escala pequeña (fracciones/porcentajes) se normalizan para que el uso real mande sobre los bonos fijos de sinergia. Si un Pokémon no aparece en los datos, el motor arma el mejor set por rol/sinergia. Los equipos de referencia con Pokepaste (verificados o hallados por la web) usan los sets reales del paste.
- **Reversión Primigenia (Gen 6/7)**: Groudon/Kyogre llevan Orbe Roja/Azul solo si el formato permite la orbe (`pool["legal_items"]`); no cuentan como Mega, sí como restringidos, y la carta lleva la etiqueta `primal` (PRIMAL).
- **Dynamax / Gigamax (Gen 8)**: el motor etiqueta (`dynamax`, `gigantamax`) al único Pokémon que lo usará, excluyendo a Zacian, Zamazenta y Eternatus; el frontend lo muestra como la Mega, el Z o la Tera.
- **Megas múltiples**: Gen 6/7 y Pokémon Champions permiten varias Megas en el equipo (solo una evoluciona por combate). El generador usa 1 por defecto y 2 si se piden, si la referencia las trae o si la segunda complementa la cobertura de la primera (`megas_complement`). El tope duro sigue siendo `max_megas_rule`.
- Cuántos se llevan a batalla (`picked_team_size`): 4 en VGC/dobles oficiales, 3 en BSS/Battle Spot Singles, 6 en Smogon.

## Adaptación por generación y formato
- `src/core/gen_data.py`: única fuente de verdad de qué existe en cada generación (formas, movimientos, objetos, aprendizajes).
- `src/core/archetypes.py`: arquetipos calculados con lo que hay en el formato (clima, terrenos, Trick Room, hazards, redirección...).
  Se comprueba si lo pedido es posible (se adapta o se rechaza con mensaje) y al final se verifica qué se logró.
- El validador aplica bans compuestos ("A ++ B", "A + B") y las cláusulas de Baton Pass, Swagger y Accuracy Moves.
- Gen 1 y 2: los datos de aprendizaje solo traen códigos desde Gen 3, así que se usan los movimientos que existían
  en esa generación y que la especie aprende en cualquier otra (mejor esfuerzo).
