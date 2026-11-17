# 14 · Aceptación: Ningún endpoint declara su esquema de respuesta

Ficha: [14-sin-response-model.md](14-sin-response-model.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Las rutas de `routes_jobs.py`, `routes_settings.py`, `routes_auth.py` y `routes_users.py` que devuelven JSON tienen `response_model` (comprobado con un test que recorre `app.routes`).
  - Verificado: `test_json_routes_declare_response_model` en verde (21 rutas JSON con `response_model`; `events`, `download`, `report` y `preview` sin él); falla sin el cambio. Recorre `router.routes` de los cuatro routers porque FastAPI 0.163 incluye los routers de forma perezosa y `app.routes` no lista sus rutas.
- [x] Test nuevo: las respuestas de `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/auth/me` y `GET /api/settings` son idénticas a las de antes del cambio (snapshot guardado en el test).
  - Verificado: `tests/test_response_snapshots.py` (4 tests) compara byte a byte con `tests/snapshots/*.json`, generados con el código anterior: 3 trabajos (translate/digitize/prepare, con y sin `null`), el listado, `auth/me` de user y admin, `settings` admin y user y una página de `GET /api/users`; en verde antes y después del cambio. En el contenedor desplegado, el JSON del libro #1 y de las 4 cuentas reales valida contra `JobRead`/`UserRead` sin perder ni cambiar campos (solo lectura).
- [x] `/openapi.json` describe el esquema 200 de `GET /api/jobs/{job_id}` con sus campos.
  - Verificado: `test_openapi_describes_job_read` en verde y, desplegado, `curl -s localhost:8000/openapi.json` → `$ref: #/components/schemas/JobRead` con sus 17 propiedades.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 183 passed, 1 skipped, 5 deselected (antes 177 passed + 6 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde dentro de la suite.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos, reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200, el OpenAPI servido describe `JobRead` y `GET /api/settings` sin sesión sigue en 401.
- [x] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
  - Verificado: `tests/test_api.py` y `tests/test_jobs_upload.py` en verde dentro de la suite (subida directa y por S3, progreso y descarga PDF, ahora a través de `response_model`); cancelar y reanudar, en `test_auth_matrix.py`/`test_admin.py`, también en verde. La descarga EPUB no pasa por esos tests, pero `download` no lleva `response_model` y no cambia. En la app con cuenta `user`: no comprobado (cuentas QA no autorizadas); el frontend no cambia porque el JSON es idéntico.
