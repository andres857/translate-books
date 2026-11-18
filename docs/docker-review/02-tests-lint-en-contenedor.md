# 02 · Tests y lint solo corren con herramientas del host

- **Severidad:** Medio
- **Categoría:** Herramientas
- **Estado:** abierto
- **Ubicación:** `.claude/skills/deploy/SKILL.md` (paso 1), `backend/Dockerfile` (instala solo `dependencies`, sin `dev`), `frontend/Dockerfile`
- **Aceptación:** [02-tests-lint-en-contenedor.aceptacion.md](02-tests-lint-en-contenedor.aceptacion.md)

## Problema

La skill `deploy` y todas las fichas anteriores ejecutan `backend/.venv/bin/pytest`, `ruff` y `npx`/`npm` del host. La
imagen del backend no incluye pytest ni ruff, y la del frontend de producción no tiene devDependencies.

## Cómo reproducirlo

`docker compose exec api python -m pytest` → `No module named pytest`.

## Impacto

Sin el entorno local no se puede verificar nada; además los tests corren con versiones distintas a la imagen (Tesseract, fuentes, Calibre).

## Corrección propuesta

Un target o servicio de herramientas: backend con `pip install .[dev]` (stage `dev`/`test` en `backend/Dockerfile`) y frontend con devDependencies (stage `dev` de #01). Comandos documentados, p. ej. `docker compose -f … run --rm api-test pytest …`, `… ruff check app tests`, `… frontend npm run lint|test|build`, `tsc` y `check.mjs` (montando `handoff/`). Los tests usan su propia BD temporal (como hoy `tests/output`), nunca `data/app.db`. Actualizar la skill `deploy` para usar estos comandos.

## Notas

Reutilizar el stage `dev` de #01 si encaja. `tests/output` debe quedar fuera de la imagen (`.dockerignore`) y fuera de `./data`.
