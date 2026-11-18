# 09 · Aceptación: Las FK no definen qué pasa al borrar y el borrado de un libro carga todo en memoria

Ficha: [09-fks-sin-ondelete.md](09-fks-sin-ondelete.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `sqlite3` sobre una copia migrada: `PRAGMA foreign_key_list(pages)` muestra `on_delete = CASCADE` hacia jobs; igual segments→pages y playground_attempts→playground_runs.
  - Verificado (copia migrada y, tras el deploy, `data/app.db` en solo lectura): pages→jobs CASCADE, segments→pages CASCADE, playground_attempts→playground_runs CASCADE; jobs→documents, jobs→users, playground_runs→jobs y playground_attempts→jobs RESTRICT. En la copia, `DELETE FROM jobs` con FK activas deja 0 páginas y 0 bloques y `DELETE FROM documents` falla («FOREIGN KEY constraint failed»).
- [x] `PRAGMA index_list(glossary)` y `PRAGMA index_list(protected_terms)` incluyen un índice sobre `document_id`.
  - Verificado: `ix_glossary_document_id` y `ix_protected_terms_document_id` (junto a los únicos `uq_glossary_doc_source` y `uq_protected_terms_doc_term` de #10), en la copia y en `data/app.db` tras el deploy.
- [x] Test nuevo con `count_queries`: `DELETE /api/jobs/{id}` hace un número de queries que **no depende** del número de bloques (≤ 25 con el PDF de prueba) y no quedan páginas ni bloques del trabajo.
  - Verificado: `test_delete_job_queries_do_not_grow_with_segments` (tests/test_admin.py): 14 queries con el PDF de prueba y 14 con 20 páginas y 200 bloques más, ningún `DELETE FROM pages/segments` y 0 filas del trabajo. Sin `passive_deletes` falla (22 frente a 42).
- [x] Upgrade → downgrade → upgrade sobre una copia de la BD real sin errores y con el mismo número de filas en cada tabla antes y después.
  - Verificado: copia con la API de backup de sqlite3 (`file:data/app.db?mode=ro`); las mismas filas por tabla en los cuatro estados (192 páginas, 3345 bloques, 149 de glosario, 2141 de caché…) y contenido idéntico (hash por tabla) tras upgrade→downgrade→upgrade; índices iguales tras el downgrade y tras el segundo upgrade.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 171 passed, 1 skipped, 5 deselected (170 + 1 nuevo).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: migración `f3b5d7e9a1c4` (sobre `e1f3a5c7b9d2`); upgrade → downgrade -1 → upgrade sin errores en la copia; `foreign_key_check` vacío e `integrity_check` ok en cada paso.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde (y falla si se quita un `ondelete` del modelo: compara las FK).
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos; copia `data/app.db.bak-review09`; worker parado, `api` reconstruida (migra al arrancar) y luego worker; health `{"ok":true}`, `/login` 200. En solo lectura: versión `f3b5d7e9a1c4`, FK e índices esperados, mismas filas por tabla que antes, `foreign_key_check` vacío, `integrity_check` ok.
- [x] Regresión: borrar un libro QA desde la app (admin) sigue funcionando y deja la BD sin filas suyas.
  - Verificado (parte automática): `test_delete_job_endpoint_refuses_active_and_removes_book` y el test nuevo en verde.
  - Verificado (app desplegada): borrar desde la app (Chrome como qa-admin) los libros QA: #4 (preparado, con 1 bloque, 1 evaluación y 1 intento del Playground, 1 entrada de glosario y 1 término propios) desde el Playground («Eliminar …» → confirmar) y #3 (1 página, glosario y término propios) y #2 (120 páginas) desde Inicio («Eliminar» → «Se eliminó «original».», `/api/jobs/N` 404). En `data/app.db` (solo lectura): 0 filas en jobs, pages, segments, playground_runs, playground_attempts, documents, glossary y protected_terms para los tres; sin páginas ni bloques huérfanos; sin carpetas `outputs/job_2..4` ni sus `uploads/<sha>`; el libro #1 sigue con 192 páginas, 3345 bloques y 149 entradas de glosario.
