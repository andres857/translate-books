# 14 · Aceptación: Ningún endpoint declara su esquema de respuesta

Ficha: [14-sin-response-model.md](14-sin-response-model.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Las rutas de `routes_jobs.py`, `routes_settings.py`, `routes_auth.py` y `routes_users.py` que devuelven JSON tienen `response_model` (comprobado con un test que recorre `app.routes`).
- [ ] Test nuevo: las respuestas de `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/auth/me` y `GET /api/settings` son idénticas a las de antes del cambio (snapshot guardado en el test).
- [ ] `/openapi.json` describe el esquema 200 de `GET /api/jobs/{job_id}` con sus campos.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
