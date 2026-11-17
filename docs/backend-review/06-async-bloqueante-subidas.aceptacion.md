# 06 · Aceptación: Las subidas directas bloquean el event loop

Ficha: [06-async-bloqueante-subidas.md](06-async-bloqueante-subidas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `grep -n "async def" backend/app/api/routes_jobs.py backend/app/api/routes_files.py` ya no lista `create_job` ni `upload_file`, o su trabajo síncrono va dentro de `run_in_threadpool`.
  - Verificado: el grep solo lista `job_events` y su `gen()` (SSE, fuera de esta ficha, #07); `create_job` y `upload_file` son `def` y leen de `file.file`. `test_direct_uploads_run_in_threadpool` (tests/test_api.py) fija que no son corrutinas.
- [x] Test nuevo o medición: durante una subida de ≥ 50 MB a `POST /api/jobs`, `GET /api/health` responde en < 200 ms (anotar la medida).
  - Verificado (medición con uvicorn real en `127.0.0.1:8765`, BD y `DATA_DIR` temporales, `FAKE_TRANSLATOR=true`, sin worker; PDF nuevo de 96 MiB por pasada —una página con imagen de ruido— para que el SHA-256 y la escritura en disco ocurran siempre; `/api/health` sondeado cada 10 ms durante la subida; 3 pasadas): antes del cambio, latencia máxima de health durante la subida **201 / 192 / 148 ms** (mediana 2,1-2,7 ms); después, **47 / 48 / 52 ms** (mediana 2,4-2,6 ms). En reposo, máx. 2,6-4,1 ms. Subida: 200 en 0,6-0,8 s en ambos casos. Lo que queda (~50 ms) es el análisis multipart de Starlette, que ocurre antes del handler (ver Notas de la ficha).
- [x] Los límites siguen: un archivo mayor que `MAX_UPLOAD_MB` → 413; un no-PDF → 400 (tests existentes en verde).
  - Verificado: `test_upload_validations` (no-PDF → 400 «PDF», sin derechos → 400) y el nuevo `test_upload_too_large_is_413` (`MAX_UPLOAD_MB`=1 → 413 «supera el límite de 1 MB») en tests/test_api.py; `test_rejects_too_large` (413) y `test_rejects_disallowed_mime` / `test_rejects_spoofed_magic_bytes` (400) en tests/test_files.py, todos en verde.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 163 passed, 1 skipped, 5 deselected (antes 161 passed + 2 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde (dentro de la suite).
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y en el contenedor `api` `inspect.iscoroutinefunction` da `False` para `create_job` y `upload_file`.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
  - Verificado (parte automática): `tests/test_api.py` y `tests/test_jobs_upload.py` en verde (dentro de la suite).
  - Pendiente de verificación manual: subir, ver progreso, cancelar, reanudar y descargar como `user` en localhost:3100 (cuentas QA no autorizadas en esta tarea).
