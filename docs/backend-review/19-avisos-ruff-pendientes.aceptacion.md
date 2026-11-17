# 19 · Aceptación: Avisos de ruff previos silenciados por archivo

Ficha: [19-avisos-ruff-pendientes.md](19-avisos-ruff-pendientes.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `backend/pyproject.toml` ya no tiene `[tool.ruff.lint.per-file-ignores]` (o solo entradas justificadas con un comentario) y `.venv/bin/ruff check app tests` → `All checks passed!`.
- [ ] Cada `zip()` marcado lleva `strict=True` o `strict=False` según si las longitudes deben coincidir (revisión del diff).
- [ ] Decidido si se activa `BLE` (+`RUF100`); si se activa, ningún `# noqa: BLE001` sobra.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: el pipeline (`tests/test_pipeline.py`, `tests/test_layout.py`, `tests/test_digitize.py`) y el Playground (`tests/test_playground*.py`) en verde.
