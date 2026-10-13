

## Novedades
- **Chat conversacional** (`POST /api/chat`): habla normal, pide un equipo y luego pide cambios ("cambia X por Y", "dale Choice Scarf a Garchomp"). Funciona en español, inglés y francés.
- **Validador final** (`src/core/team_validator.py`): comprueba y corrige reglas del formato (Megas, restringidos, ítems duplicados, bans, movimientos aprendibles, cláusulas de sueño/OHKO/evasión, EVs).
- Correcciones de datos: Megapiedras, Megas Z-A mal marcadas, Pokémon "Illegal"/formas de combate en Gen 9, movimientos heredados de preevoluciones.

## Adaptación por generación y formato
- `src/core/gen_data.py`: única fuente de verdad de qué existe en cada generación (formas, movimientos, objetos, aprendizajes).
- `src/core/archetypes.py`: arquetipos calculados con lo que hay en el formato (clima, terrenos, Trick Room, hazards, redirección...).
  Se comprueba si lo pedido es posible (se adapta o se rechaza con mensaje) y al final se verifica qué se logró.
- El validador aplica bans compuestos ("A ++ B", "A + B") y las cláusulas de Baton Pass, Swagger y Accuracy Moves.
- Gen 1 y 2: los datos de aprendizaje solo traen códigos desde Gen 3, así que se usan los movimientos que existían
  en esa generación y que la especie aprende en cualquier otra (mejor esfuerzo).
