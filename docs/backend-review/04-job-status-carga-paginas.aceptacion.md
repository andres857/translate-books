# 04 · Aceptación: El estado de un trabajo carga todas sus páginas y el listado hace N+1

Ficha: [04-job-status-carga-paginas.md](04-job-status-carga-paginas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo con `count_queries`: `GET /api/jobs/{id}` hace **≤ 5 queries** y no carga páginas que no necesitan revisión (asegurado comprobando que la query de páginas lleva `needs_review`).
- [ ] Test nuevo: `GET /api/jobs` con 10 trabajos hace **≤ 6 queries** (no crece con el número de trabajos).
- [ ] Test nuevo: la respuesta de `GET /api/jobs/{id}` es idéntica (mismo JSON) antes y después, incluida `review_pages`.
- [ ] Medición sobre una copia de la BD real: `GET /api/jobs` y `GET /api/jobs/1` con el número de queries anotado en la línea «Verificado».

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
