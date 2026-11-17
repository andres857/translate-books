# 18 · Aceptación: Variables reutilizadas y un diccionario de locks que crece sin límite

Ficha: [18-estilo-menor.md](18-estilo-menor.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `presign_book` y `pages` no reasignan el parámetro `p` (revisión del diff).
- [ ] `_epub_locks` no crece con cada trabajo distinto (test: 100 trabajos distintos dejan el dict en ≤ 1 elemento tras terminar, o se usa una estructura débil).
- [ ] Descargar EPUB dos veces en paralelo del mismo trabajo genera el archivo una sola vez (test existente o nuevo).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: subir un PDF, ver el progreso, cancelar, reanudar y descargar (PDF/EPUB) como `user` siguen funcionando (`tests/test_api.py`, `tests/test_jobs_upload.py` en verde).
