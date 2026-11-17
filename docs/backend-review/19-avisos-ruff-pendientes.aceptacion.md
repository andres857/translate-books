# 19 · Aceptación: Avisos de ruff previos silenciados por archivo

Ficha: [19-avisos-ruff-pendientes.md](19-avisos-ruff-pendientes.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `backend/pyproject.toml` ya no tiene `[tool.ruff.lint.per-file-ignores]` (o solo entradas justificadas con un comentario) y `.venv/bin/ruff check app tests` → `All checks passed!`.
  - Verificado: sección eliminada en 26b9542; `ruff check app tests --no-cache` → `All checks passed!` (los 5 B023 quedan con `# noqa: B023` justificado en línea).
- [x] Cada `zip()` marcado lleva `strict=True` o `strict=False` según si las longitudes deben coincidir (revisión del diff).
  - Verificado: diff de 26b9542: 11 `zip()` con `strict=` (5 `True` donde coinciden por construcción o ya se comprueban, 6 `False` en pares consecutivos y variantes/resultados); criterio en las Notas.
- [x] Decidido si se activa `BLE` (+`RUF100`); si se activa, ningún `# noqa: BLE001` sobra.
  - Verificado: `select` incluye `BLE` y `RUF100` (8f0a64c); 15 `# noqa: BLE001` innecesarios quitados y `ruff check app tests` → `All checks passed!` (RUF100 marcaría cualquiera que sobre).

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 190 passed, 1 skipped, 5 deselected (igual que antes; la ficha no añade tests).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos; `api` y `worker` reconstruidos; health `{"ok":true}`, `/login` 200 y el contenedor `api` contiene el `strict=False` nuevo de `playground.py`.
- [x] Regresión: el pipeline (`tests/test_pipeline.py`, `tests/test_layout.py`, `tests/test_digitize.py`) y el Playground (`tests/test_playground*.py`) en verde.
  - Verificado: `tests/test_pipeline.py tests/test_layout.py tests/test_digitize.py tests/test_playground*.py` → 40 passed.
