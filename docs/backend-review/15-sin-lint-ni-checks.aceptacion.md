# 15 · Aceptación: Sin linter, sin chequeo de tipos y sin control de divergencia del esquema

Ficha: [15-sin-lint-ni-checks.md](15-sin-lint-ni-checks.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `cd backend && .venv/bin/ruff check app tests` → `All checks passed!` (o se documenta en esta ficha la lista de reglas excluidas y por qué).
- [ ] Test nuevo `test_alembic_check`: migra una BD temporal a `head` y `alembic check` no detecta operaciones pendientes.
- [ ] `count_queries` existe en `tests/conftest.py` y lo usa al menos un test.
- [ ] La skill `deploy` (paso de comprobaciones) incluye `ruff check` y el resto de pruebas del backend.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: ninguna funcional.
