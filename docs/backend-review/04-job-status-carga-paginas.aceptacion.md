# 04 · Aceptación: El estado de un trabajo carga todas sus páginas y el listado hace N+1

Ficha: [04-job-status-carga-paginas.md](04-job-status-carga-paginas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo con `count_queries`: `GET /api/jobs/{id}` hace **≤ 5 queries** y no carga páginas que no necesitan revisión (asegurado comprobando que la query de páginas lleva `needs_review`).
  - Verificado: `test_job_status_queries_only_pages_to_review` (tests/test_api.py) en verde: una sola query sobre `pages`, con `needs_review` y sin columnas como `width`/`kind`; falla con el código anterior (commit 03b5cbb).
- [x] Test nuevo: `GET /api/jobs` con 10 trabajos hace **≤ 6 queries** (no crece con el número de trabajos).
  - Verificado: `test_list_jobs_queries_do_not_grow_with_jobs` en verde (mismas queries con 1 y con 10 trabajos, ≤ 6); con el código anterior hacía 23.
- [x] Test nuevo: la respuesta de `GET /api/jobs/{id}` es idéntica (mismo JSON) antes y después, incluida `review_pages`.
  - Verificado: `test_job_status_json_unchanged` (JSON completo esperado, páginas creadas en orden no correlativo, y la misma entrada en `GET /api/jobs`) pasa con el código anterior y con el nuevo. Sobre la copia de la BD real el sha256 de ambas respuestas es igual antes y después.
- [x] Medición sobre una copia de la BD real: `GET /api/jobs` y `GET /api/jobs/1` con el número de queries anotado en la línea «Verificado».
  - Verificado (copia con la API de backup de sqlite3, `mode=ro`; 1 libro, 192 páginas, 1 a revisar): `GET /api/jobs` 5 → **4** queries (ya no crece por trabajo); `GET /api/jobs/1` 5 → **5** queries, pero la de páginas pasa de traer las 192 filas completas a `SELECT pages.job_id, pages.number, pages.review_reasons … WHERE … needs_review` (1 fila). Medido en este equipo, el contador cuenta 2 queries de sesión, no 3 (sin escritura de `last_seen`).

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 159 passed, 1 skipped, 5 deselected (antes 156 passed + 3 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde (dentro de la suite).
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y el contenedor `api` contiene `_review_pages`.
- [x] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
  - Verificado (parte automática): `tests/test_api.py` y `tests/test_jobs_upload.py` en verde (dentro de la suite).
  - Verificado (app desplegada): Chrome como qa-user: login → «Libros» sin ningún libro ajeno (`/api/jobs` vacío al empezar, `/api/jobs/1` 404); subir un PDF QA de 120 páginas en blanco solo con imagen (OCR local, 0 bloques, 0 llamadas al modelo) con «Traducir libro» → /jobs/2, la barra de progreso avanza por polling (0 → 4 %); «Cancelar» → `cancelled` y sigue `cancelled` 4 s después (el worker no lo pisa), aparece «Reanudar» → `running` → «Tu libro está listo»; «Descargar PDF» (`original (ES).pdf`, %PDF) y «Kindle (EPUB)» (`original (ES).epub`, PK); `/api/jobs/2/events` 404; el inicio solo lista qa-be-imagenes.pdf; sin errores de página.
