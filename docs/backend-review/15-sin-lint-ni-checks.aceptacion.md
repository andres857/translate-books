# 15 · Aceptación: Sin linter, sin chequeo de tipos y sin control de divergencia del esquema

Ficha: [15-sin-lint-ni-checks.md](15-sin-lint-ni-checks.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `cd backend && .venv/bin/ruff check app tests` → `All checks passed!` (o se documenta en esta ficha la lista de reglas excluidas y por qué).
  - Verificado: ruff 0.17.5 → `All checks passed!`. Reglas excluidas y motivo en las Notas de la ficha (E501, E741, E731 en todo el código; B904/B905/B023/B007/F841 solo en los archivos que ya las tenían, pendientes en la ficha #19).
- [x] Test nuevo `test_alembic_check`: migra una BD temporal a `head` y `alembic check` no detecta operaciones pendientes.
  - Verificado: `tests/test_tooling.py::test_alembic_check` en verde («No new upgrade operations detected»). Prueba en negativo: con `index=True` temporal en `GlossaryEntry.document_id` el test falla con `add_index ix_glossary_document_id` (cambio revertido).
- [x] `count_queries` existe en `tests/conftest.py` y lo usa al menos un test.
  - Verificado: `count_queries()` (context manager sobre `before_cursor_execute` del engine de la app; da `count` y `statements`); lo usa `test_glossary_list_queries_do_not_grow_with_entries` (mismas queries en `GET /api/glossary` con 1 y con 5 entradas), en verde.
- [x] La skill `deploy` (paso de comprobaciones) incluye `ruff check` y el resto de pruebas del backend.
  - Verificado: `.claude/skills/deploy/SKILL.md`, paso 1: `.venv/bin/ruff check app tests` y `.venv/bin/python -m pytest -q -m "not slow and not s3"` (que incluye `test_alembic_check`).

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 156 passed, 1 skipped, 5 deselected (antes 154 passed + 2 nuevos), también tras el commit de arreglos automáticos.
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos, reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y el contenedor `api` ya no tiene `import io` en `app/pipeline/ocr.py`.
- [x] Regresión: ninguna funcional.
  - Verificado: los cambios de `app/` son solo orden de imports y un import sin usar; la suite completa sigue en verde.
