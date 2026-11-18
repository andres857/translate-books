# 01 · Desarrollar exige Python y Node en el equipo

- **Severidad:** Medio
- **Categoría:** Experiencia de desarrollo
- **Estado:** resuelto · commit(s) `aa65741`
- **Ubicación:** `README.md` («Desarrollo local (sin Docker)»), `docker-compose.yml`, `frontend/Dockerfile`, `backend/Dockerfile`
- **Aceptación:** [01-compose-dev-recarga.aceptacion.md](01-compose-dev-recarga.aceptacion.md)

## Problema

Hoy los contenedores solo sirven builds de producción: cualquier cambio exige reconstruir imágenes (minutos con
el build de Next y la imagen del backend de 2,45 GB). Para iterar rápido hay que instalar en el host un `.venv`
(`pip install -e backend[dev]`) y `npm install`, más Tesseract, OCRmyPDF y Calibre si se toca el pipeline.

## Cómo reproducirlo

Seguir el README en un equipo limpio con solo Docker: la sección de desarrollo no funciona sin Python 3.12, Node 22 y paquetes del sistema.

## Impacto

Cada cambio cuesta un rebuild o una instalación local que diverge de la imagen (versiones de Tesseract, fuentes, Calibre).

## Corrección propuesta

Añadir `compose.dev.yml` (override) con: `api` con `uvicorn --reload` y `backend/` montado; `worker` con el código montado y reinicio sencillo (p. ej. `watchfiles` si ya está disponible por uvicorn[standard], o documentar `docker compose restart worker`); `frontend` con un target `dev` en el Dockerfile (`next dev`), `frontend/` montado y `node_modules` en un volumen anónimo. Mismos puertos que producción (3100/8000) y misma BD/volumen. Documentar `docker compose -f docker-compose.yml -f compose.dev.yml up` en el README y cómo volver al stack de producción.

## Notas

No cambiar el stack de producción salvo para añadir el target `dev` (el build de producción debe seguir igual). Next 16: leer `frontend/AGENTS.md` y `node_modules/next/dist/docs/` antes de tocar la config de desarrollo. El rewrite `/api` usa `BACKEND_URL` en tiempo de build; en dev se evalúa al arrancar `next dev`.

Decisiones (opción recomendada):

- Worker **sin recarga automática**: comparte la BD con producción y reiniciarlo corta la traducción en curso; se
  documenta `active-jobs` + `restart worker`.
- En dev se montan solo `backend/app`, `alembic/`, `alembic.ini`, `pyproject.toml`, `tests/` y `scripts/`, no
  `backend/` entero: `config.py` lee `.env` del directorio de trabajo y leería `backend/.env` (valores del modo
  host, ficha #05); además así no entran `.venv` ni `data`.
- `backend/Dockerfile` pasa a stages `base` → `dev` → final (producción, mismo contenido y metadatos que antes);
  `frontend/Dockerfile` añade `dev` entre `build` y el final, que sigue intacto (USER node, HEALTHCHECK). Sin
  `target`, compose construye el último stage. Imágenes dev con otro nombre (`traductor-backend:dev`,
  `traductor-frontend:dev`): no pisan las de producción.
- El backend dev instala las dependencias de `[project.dependencies]` + `[dev]` (pytest, ruff) leyendo
  `pyproject.toml`, como producción, en vez de `pip install .[dev]`: no instala el paquete en site-packages, así
  que siempre se importa el código de `/app` (montado o copiado).

Reutilización en #02 (tests y lint en contenedor): ambos stages `dev` copian el código y llevan las herramientas.

- Backend (`traductor-backend:dev`, usuario `app`, cwd `/app`; probado `ruff 0.17.5`, `pytest 9.2.0`, `ruff check
  app tests` limpio): p. ej. `docker compose -f docker-compose.yml -f compose.dev.yml run --rm --no-deps api
  sh -c 'ruff check app tests && python -m pytest -q -m "not slow and not s3"'` (con los montajes de código) o
  `docker build --target dev backend` + `docker run --rm` sin montajes. Ojo: el `run` del servicio `api` hereda
  `./data:/data` y `DATABASE_URL`; los tests deben seguir usando su BD temporal.
- Frontend (`traductor-frontend:dev`, usuario `node`, devDependencies completas; probado `tsc 5.9.3`, `vitest
  4.0.8`): `… run --rm --no-deps frontend sh -c 'npx tsc --noEmit && npm run lint && npm run test && npm run build'`;
  `check.mjs` está en `handoff/`, fuera del contexto `frontend/`: #02 tendrá que montarlo (p. ej. `./handoff:/handoff`).
