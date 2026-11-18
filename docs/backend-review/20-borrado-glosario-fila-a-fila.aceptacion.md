# 20 · Aceptación: Al borrar un libro, glosario, términos e intentos se borran fila a fila

Ficha: [20-borrado-glosario-fila-a-fila.md](20-borrado-glosario-fila-a-fila.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo con `count_queries`: `DELETE /api/jobs/{id}` hace el mismo número de queries con 1 y con 50 entradas de glosario y términos del documento, y con 0 y 5 intentos del Playground.
  - Verificado: `test_delete_job_queries_do_not_grow_with_glossary_or_attempts` (tests/test_admin.py): 17 queries en los dos casos; glosario, términos e intentos solo aparecen en un `DELETE FROM <tabla> WHERE <tabla>.document_id/job_id = ?` (más el `SELECT playground_attempts.pdf`). Con el código anterior falla (18 frente a 17 y SELECT de filas completas; los DELETE por id el ORM los agrupa en un executemany, por eso el test comprueba también las sentencias).
- [x] Tras el borrado no quedan entradas de glosario ni términos del documento, ni intentos del trabajo, y los PDF de los intentos se borran del disco.
  - Verificado: el mismo test cuenta 0 entradas de glosario, 0 términos, 0 intentos y 0 evaluaciones de ambos trabajos, y los 5 PDF de intentos ya no existen en disco.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 190 passed, 1 skipped, 5 deselected (189 + 1 nuevo).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración (sin cambio de esquema).
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde dentro de la suite.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; `api` y `worker` reconstruidos; health `{"ok":true}`, `/login` 200 y el contenedor `api` sirve el `delete(PlaygroundAttempt)` nuevo.
- [x] Regresión: borrar un libro QA desde la app (admin) sigue funcionando y deja la BD sin filas suyas.
  - Verificado (parte automática): `test_delete_job_endpoint_refuses_active_and_removes_book`, `test_delete_job_queries_do_not_grow_with_segments` y el test nuevo en verde.
  - Verificado (app desplegada): borrar desde la app (Chrome como qa-admin) los libros QA: #4 (preparado, con 1 bloque, 1 evaluación y 1 intento del Playground, 1 entrada de glosario y 1 término propios) desde el Playground («Eliminar …» → confirmar) y #3 (1 página, glosario y término propios) y #2 (120 páginas) desde Inicio («Eliminar» → «Se eliminó «original».», `/api/jobs/N` 404). En `data/app.db` (solo lectura): 0 filas en jobs, pages, segments, playground_runs, playground_attempts, documents, glossary y protected_terms para los tres; sin páginas ni bloques huérfanos; sin carpetas `outputs/job_2..4` ni sus `uploads/<sha>`; el libro #1 sigue con 192 páginas, 3345 bloques y 149 entradas de glosario.
