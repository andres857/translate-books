# 06 · Aceptación: Las subidas directas bloquean el event loop

Ficha: [06-async-bloqueante-subidas.md](06-async-bloqueante-subidas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `grep -n "async def" backend/app/api/routes_jobs.py backend/app/api/routes_files.py` ya no lista `create_job` ni `upload_file`, o su trabajo síncrono va dentro de `run_in_threadpool`.
- [ ] Test nuevo o medición: durante una subida de ≥ 50 MB a `POST /api/jobs`, `GET /api/health` responde en < 200 ms (anotar la medida).
- [ ] Los límites siguen: un archivo mayor que `MAX_UPLOAD_MB` → 413; un no-PDF → 400 (tests existentes en verde).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
