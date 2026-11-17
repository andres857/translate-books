# 02 · Aceptación: El worker puede sobrescribir una cancelación con «done», «paused» o «failed»

Ficha: [02-worker-pisa-cancelacion.md](02-worker-pisa-cancelacion.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: si el job pasa a `cancelled` mientras el worker procesa (antes del cierre), al terminar `process()` el estado sigue siendo `cancelled`.
- [ ] Test nuevo: lo mismo con un fallo (excepción en el pipeline): un job `cancelled` no pasa a `failed`.
- [ ] Test nuevo: una evaluación del Playground cancelada durante `execute()` sigue `cancelled` (no `done` ni `paused`).
- [ ] Sin cancelación, un job termina en `done` y una evaluación en `done` (tests existentes en verde).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
