# 12 · Aceptación: PDFs y sesiones de base de datos que no se cierran

Ficha: [12-recursos-sin-cerrar.md](12-recursos-sin-cerrar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `grep -n "pymupdf.open(" backend/app/api/*.py` muestra solo usos con `with`.
  - Verificado: 4 resultados, todos `with pymupdf.open(...) as pdf:`: routes_admin.py:56, routes_playground.py:335, routes_jobs.py:136 (subida, antes sin `with`) y routes_jobs.py:400 (`preview`).
- [x] `grep -n "SqlCache(SessionLocal())" backend/app` no devuelve resultados (la sesión de la caché se cierra).
  - Verificado: `grep -rn` vacío. Las tres llamadas del worker (traducción, recomposición y digitalización) usan `with SessionLocal() as cache_s:` + `SqlCache(cache_s)`. Medición en proceso (script con la BD temporal, 5 trabajos con el PDF de prueba y `worker.process`): antes del cambio quedaban **2** conexiones prestadas del pool (`engine.pool.checkedout()`) y 21 descriptores; después, **0** y 15. El test nuevo `test_worker_and_preview_close_resources` (tests/test_api.py) desactiva el GC, procesa un trabajo y exige que no quede ninguna conexión prestada. Falla sin el cambio y pasa con él.
- [x] Test o medición: 200 peticiones a `/api/jobs/{id}/pages/1/preview` no aumentan los descriptores abiertos del proceso en más de 5 (anotar antes/después).
  - Verificado (uvicorn real en `127.0.0.1:8766`, `DATABASE_URL`/`DATA_DIR` temporales en el scratchpad, `FAKE_TRANSLATOR=true`; trabajo procesado con `build_sample_pdf` + `worker.process`; 2 previews de calentamiento y luego 200 a las páginas 1-5, todas 200; servidor parado por su PID): antes del cambio **17 → 17** descriptores y después **17 → 17**. En CPython el recuento de referencias ya cerraba el documento al terminar cada petición, así que no había crecimiento que medir (ver Notas de la ficha). El mismo test fija que los PDF abiertos por `preview` (200 y 404) y por la subida quedan `is_closed`.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 164 passed, 1 skipped, 5 deselected (antes 163 passed + 1 nuevo).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde (dentro de la suite).
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200. En el contenedor `api`, `app/worker.py` tiene 3 `with SessionLocal() as cache_s` y `routes_jobs.py:400` es `with pymupdf.open(path) as pdf:`.
- [ ] Regresión: la vista previa de páginas y la traducción/recomposición con el traductor falso siguen funcionando.
  - Verificado (parte automática): `test_upload_process_download` (preview original 200 PNG), el test nuevo (preview traducida 200, página inexistente 404) y los de recomposición de `tests/test_admin.py` / `tests/test_worker_cancel.py` en verde con el traductor falso, igual que la medición (200 previews con 200).
  - Pendiente de verificación manual: ver la vista previa y recomponer una página en localhost:3100 (cuentas QA no autorizadas en esta tarea).
