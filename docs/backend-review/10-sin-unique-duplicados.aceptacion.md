# 10 · Aceptación: Nada en la BD impide duplicados en bloques, glosario y términos

Ficha: [10-sin-unique-duplicados.md](10-sin-unique-duplicados.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: añadir dos veces la misma entrada de glosario (mismo libro o global, distinto uso de mayúsculas) → la segunda responde **409** y hay una sola fila.
  - Verificado: `test_glossary_duplicate_is_409[global|book]` (tests/test_admin.py): «Ascendant» y luego « ascendant » → 409 y una sola fila con `lower(source)='ascendant'` en ese ámbito. `test_glossary_same_term_global_and_per_book_is_allowed`: el mismo término global y en un libro sí se admite. Los 5 tests nuevos de duplicados fallan sin la migración (BD de prueba aparte) y pasan con ella.
- [x] Test nuevo: lo mismo con términos protegidos.
  - Verificado: `test_protected_term_duplicate_is_409[global|book]`: «Chiron» y luego « Chiron » (otra categoría) → 409 y una sola fila. Los términos distinguen mayúsculas (ver Notas de la ficha), así que el test no usa otra capitalización.
- [x] Test nuevo: insertar dos `Segment` con el mismo `seg_key` en la misma página lanza `IntegrityError`.
  - Verificado: `test_duplicate_seg_key_in_page_raises_integrity_error`: dos `Segment(seg_key="dup_s001")` en la página 1 → `IntegrityError` al hacer commit y, tras el rollback, ninguna fila.
- [x] La respuesta 409 no contiene texto de SQLite (`UNIQUE constraint`, nombres de tabla).
  - Verificado: los tests exigen `detail == "Ese término ya existe."` y que el cuerpo no contenga `unique`, `constraint`, `sqlite`, `integrity`, `glossary` ni `protected_terms` (`_commit_new` en routes_terms.py hace rollback y lanza el 409 `from None`).
- [x] Antes de migrar, las consultas de duplicados sobre una copia de la BD real devuelven 0 filas (anotado en «Verificado»).
  - Verificado: copia con la API de backup de sqlite3 desde `file:data/app.db?mode=ro` (versión `d2e4f6a8c0b1`). `GROUP BY … HAVING COUNT(*) > 1` sobre `segments (page_id, seg_key)`, `glossary (coalesce(document_id,0), lower(source))` (también con `trim`), `protected_terms (coalesce(document_id,0), term)` (también con `lower`): **0 filas** en todas. No existe `documents.id = 0`, así que `coalesce(…, 0)` no choca con un libro real.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 170 passed, 1 skipped, 5 deselected (antes 164 passed + 6 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: migración `e1f3a5c7b9d2` sobre la copia: `d2e4f6a8c0b1` → `e1f3a5c7b9d2` (3 índices `uq_*`) → `d2e4f6a8c0b1` (sin índices) → `e1f3a5c7b9d2`, sin errores. Filas por tabla idénticas en los cuatro estados (segments 3345, glossary 149, pages 192, translation_cache 2141, users 4, auth_sessions 114, …); `foreign_key_check` vacío e `integrity_check` = ok. El DDL creado coincide con el que generan los modelos (`CreateIndex` con el dialecto sqlite).
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `All checks passed!` y `test_alembic_check` en verde («No new upgrade operations detected»). Alembic avisa de que no puede comparar en SQLite los dos índices de expresiones (los omite); el de `segments` sí se compara.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; copia previa `data/app.db.bak-review10` (API de backup de sqlite3, `integrity_check` ok, versión `d2e4f6a8c0b1`); reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200. `data/app.db` en solo lectura: versión `e1f3a5c7b9d2`, los 3 índices `uq_*` existen, mismas filas por tabla, `foreign_key_check` vacío. El contenedor `api` sirve el nuevo `routes_terms.py` («Ese término ya existe»).
- [x] Regresión: la pestaña Glosario y términos del admin permite añadir, editar y borrar entradas como antes.
  - Verificado (parte automática): `test_terms_filter`, `test_glossary_list_queries_do_not_grow_with_entries` y los tests nuevos añaden y borran entradas por la API; el frontend (`terms.tsx` → `parse` en `lib/api/http.ts`) muestra el `detail` del 409 sin cambios.
  - Verificado (app desplegada): Chrome como qa-admin en /admin/jobs/3 › «Glosario y términos» (libro QA): añadir «river → río» (Este libro), editarla a «arroyo», repetir «River» → aviso «Ese término ya existe.» y sigue 1 fila; añadir el término «Quiet» y repetirlo → «Ese término ya existe.» con 1 fila; «Quitar» los dos (y uno creado por la API) → «El glosario está vacío.» / «No hay términos protegidos manuales.» y la API devuelve listas vacías para el documento 3. No se tocó el glosario del libro #1.
