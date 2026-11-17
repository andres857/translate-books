# 02 · Aceptación: El worker puede sobrescribir una cancelación con «done», «paused» o «failed»

Ficha: [02-worker-pisa-cancelacion.md](02-worker-pisa-cancelacion.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: si el job pasa a `cancelled` mientras el worker procesa (antes del cierre), al terminar `process()` el estado sigue siendo `cancelled`.
  - Verificado: `test_cancel_before_close_keeps_cancelled` (y `test_cancel_during_recompose_keeps_cancelled` para la recomposición) en `tests/test_worker_cancel.py`: queda `cancelled` sin `output_path`; ambos fallan sin la corrección (commit f39a302).
- [x] Test nuevo: lo mismo con un fallo (excepción en el pipeline): un job `cancelled` no pasa a `failed`.
  - Verificado: `test_cancel_then_failure_does_not_become_failed`: sigue `cancelled` con `error` vacío; falla sin la corrección.
- [x] Test nuevo: una evaluación del Playground cancelada durante `execute()` sigue `cancelled` (no `done` ni `paused`).
  - Verificado: `test_playground_cancel_during_execute_keeps_cancelled` (no `done`), `test_playground_cancel_is_not_turned_into_paused` (sin saldo, no `paused`) y `test_playground_cancelled_before_start_is_not_run` (cancelada entre `claim_run` y `execute`); los tres fallan sin la corrección.
- [x] Sin cancelación, un job termina en `done` y una evaluación en `done` (tests existentes en verde).
  - Verificado: `test_without_cancel_job_ends_done`, `test_failure_without_cancel_becomes_failed`, `test_playground_without_cancel_ends_done` y los existentes (`test_admin.py`, `test_playground.py` con la pausa por saldo y su reanudación, `test_playground_compose.py`) en verde.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 149 passed, 1 skipped, 5 deselected (antes 140 passed + 9 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado (al cerrar el #15, sobre el código actual): `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos ni evaluaciones activos, reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y el contenedor `worker` contiene `close_job` y `_set_if_running`.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
  - Verificado (parte automática): `tests/test_api.py` y `tests/test_jobs_upload.py` en verde.
  - Pendiente de verificación manual: subir, cancelar, reanudar y descargar como `user` en localhost:3100 (cuentas QA no autorizadas en esta tarea).
