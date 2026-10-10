

## Novedades
- **Chat conversacional** (`POST /api/chat`): habla normal, pide un equipo y luego pide cambios ("cambia X por Y", "dale Choice Scarf a Garchomp"). Funciona en español, inglés y francés.
- **Validador final** (`src/core/team_validator.py`): comprueba y corrige reglas del formato (Megas, restringidos, ítems duplicados, bans, movimientos aprendibles, cláusulas de sueño/OHKO/evasión, EVs).
- Correcciones de datos: Megapiedras, Megas Z-A mal marcadas, Pokémon "Illegal"/formas de combate en Gen 9, movimientos heredados de preevoluciones.
