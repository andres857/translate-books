# 09 · Aceptación: Las FK no definen qué pasa al borrar y el borrado de un libro carga todo en memoria

Ficha: [09-fks-sin-ondelete.md](09-fks-sin-ondelete.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `sqlite3` sobre una copia migrada: `PRAGMA foreign_key_list(pages)` muestra `on_delete = CASCADE` hacia jobs; igual segments→pages y playground_attempts→playground_runs.
- [ ] `PRAGMA index_list(glossary)` y `PRAGMA index_list(protected_terms)` incluyen un índice sobre `document_id`.
- [ ] Test nuevo con `count_queries`: `DELETE /api/jobs/{id}` hace un número de queries que **no depende** del número de bloques (≤ 25 con el PDF de prueba) y no quedan páginas ni bloques del trabajo.
- [ ] Upgrade → downgrade → upgrade sobre una copia de la BD real sin errores y con el mismo número de filas en cada tabla antes y después.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: borrar un libro QA desde la app (admin) sigue funcionando y deja la BD sin filas suyas.
