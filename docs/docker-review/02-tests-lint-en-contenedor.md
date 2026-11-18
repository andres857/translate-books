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

Decisiones (opción recomendada):

- Servicios `backend-test` y `frontend-test` en `compose.dev.yml` con `profiles: [tools]` (no un compose.test.yml
  aparte): reutilizan las imágenes `traductor-backend:dev`/`traductor-frontend:dev` de #01 sin stage nuevo, y `up`
  no los arranca. Por defecto ejecutan la batería completa; con argumentos, un comando suelto.
- `backend-test` no hereda `x-backend`: sin `env_file` `.env`, sin `./data` y con `DATABASE_URL` apuntando a la BD
  temporal de `tests/output` y `DATA_DIR=/tmp/traductor-data`; `network_mode: none` (los tests `s3` quedan fuera).
  Monta las mismas carpetas de código que el `api` dev; `tests/output` se escribe en `backend/tests/output` del
  host con uid 1000 (ignorada por git y `.dockerignore`), como con `.venv`.
- `frontend-test` monta `frontend/` (con `node_modules` y `.next` en volúmenes anónimos, que borra `run --rm`) y
  `./handoff:/handoff:ro` para `node ../handoff/check.mjs app lib`. Con red: `next/font/google` descarga Inter en el build.
- Skill `deploy`: el contenedor es el método principal; el host con `.venv` queda como alternativa opcional.
