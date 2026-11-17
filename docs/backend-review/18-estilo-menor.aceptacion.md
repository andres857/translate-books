# 18 · Aceptación: Variables reutilizadas y un diccionario de locks que crece sin límite

Ficha: [18-estilo-menor.md](18-estilo-menor.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `presign_book` y `pages` no reasignan el parámetro `p` (revisión del diff).
  - Verificado: diff de 408fdbf: `presigned = storage_call(...)` en `presign_book` y `for pg in rows` en `pages`; `p` solo es el `Principal`.
- [x] `_epub_locks` no crece con cada trabajo distinto (test: 100 trabajos distintos dejan el dict en ≤ 1 elemento tras terminar, o se usa una estructura débil).
  - Verificado: `_epub_locks` sustituido por `_build_locks` (`WeakValueDictionary`); `test_epub_locks_do_not_grow_with_jobs` (100 trabajos distintos, el dict no crece; mismo lock para el mismo trabajo y formato) en verde; falla con el código anterior.
- [x] Descargar EPUB dos veces en paralelo del mismo trabajo genera el archivo una sola vez (test existente o nuevo).
  - Verificado: `test_concurrent_epub_downloads_build_once` (dos hilos con `Barrier`, generación falsa de 0,2 s): `build_epub_for_job` se llama una vez y ambos reciben el archivo.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 189 passed, 1 skipped, 5 deselected (187 + 2 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos; `api` y `worker` reconstruidos; health `{"ok":true}`, `/login` 200 y el contenedor `api` contiene `_build_lock`.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
  - Verificado (parte automática): `tests/test_api.py` y `tests/test_jobs_upload.py` en verde.
  - Pendiente de verificación manual: subir, cancelar, reanudar y descargar PDF/EPUB en localhost:3100 (cuentas QA no autorizadas en esta tarea).
