# 07 · Aceptación: El flujo SSE de progreso hace consultas síncronas en el loop y no se usa

Ficha: [07-sse-sin-uso.md](07-sse-sin-uso.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Si se quita: `GET /api/jobs/{id}/events` responde 404/405 y ningún test ni archivo del frontend lo referencia (`grep -rn "/events" backend/app frontend/app frontend/lib` vacío).
- [ ] Si se conserva: la consulta de cada vuelta se ejecuta con `run_in_threadpool` y un test comprueba que se corta con `event: unauthorized` al revocar la sesión.
- [ ] La decisión tomada queda escrita en las Notas de esta ficha.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
