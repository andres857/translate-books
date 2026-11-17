# 07 · Aceptación: El flujo SSE de progreso hace consultas síncronas en el loop y no se usa

Ficha: [07-sse-sin-uso.md](07-sse-sin-uso.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Si se quita: `GET /api/jobs/{id}/events` responde 404/405 y ningún test ni archivo del frontend lo referencia (`grep -rn "/events" backend/app frontend/app frontend/lib` vacío).
  - Verificado: tras desplegar, `curl localhost:8000/api/jobs/1/events` → 404 (antes, 401 sin sesión) y `test_events_endpoint_was_removed` (404/405 con sesión de dueño y sin `/events` en el OpenAPI) en verde; `grep -rn -e "/events" -e EventSource backend/app frontend/app frontend/lib` vacío, y tampoco aparece en README, `.claude/` (skill deploy) ni `docs/` fuera de `docs/backend-review`. El test del SSE se quitó; el nuevo solo comprueba que la ruta ya no existe (ver Notas).
- [x] Si se conserva: la consulta de cada vuelta se ejecuta con `run_in_threadpool` y un test comprueba que se corta con `event: unauthorized` al revocar la sesión.
  - Verificado: no aplica, se quitó (decisión del usuario).
- [x] La decisión tomada queda escrita en las Notas de esta ficha.
  - Verificado: sección «Notas» de [07-sse-sin-uso.md](07-sse-sin-uso.md): quitar el endpoint (decisión del usuario) y por qué.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 183 passed, 1 skipped, 5 deselected (antes 183: se quita el test del SSE y se añade `test_events_endpoint_was_removed`; `test_json_routes_declare_response_model` sigue en verde).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `.venv/bin/ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde dentro de la suite.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos (`app.cli active-jobs`), reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200, `/api/jobs/1/events` 404 y el `routes_jobs.py` del contenedor ya no contiene `job_events`.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
  - Verificado (parte automática): `tests/test_api.py` y `tests/test_jobs_upload.py` en verde dentro de la suite; `test_owner_sees_and_manages_own_job` (cancelar/reanudar como `user`) en verde.
  - Pendiente de verificación manual: subir, ver el progreso por polling, cancelar, reanudar y descargar con una cuenta `user` en localhost:3100 (cuentas QA no autorizadas en esta tarea).
