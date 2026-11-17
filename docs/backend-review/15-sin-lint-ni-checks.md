# 15 · Sin linter, sin chequeo de tipos y sin control de divergencia del esquema

- **Severidad:** Medio
- **Categoría:** Herramientas
- **Estado:** abierto
- **Ubicación:** `backend/pyproject.toml` (`[project.optional-dependencies] dev = ["pytest"]`)
- **Aceptación:** [15-sin-lint-ni-checks.aceptacion.md](15-sin-lint-ni-checks.aceptacion.md)

## Problema

No hay `ruff`, `mypy`/`pyright` ni `alembic check`; ningún test fija el número de queries. Hay varios
`# noqa: BLE001` que nadie comprueba.

## Cómo reproducirlo

`backend/.venv/bin/ruff --version` → no existe. `alembic check` nunca se ejecuta.

## Impacto

Errores de estilo, imports muertos y divergencias entre modelos y migraciones pasan sin aviso; el N+1 puede volver.

## Corrección propuesta

Añadir `ruff` a `dev` con configuración mínima (`E,F,I,B` y la longitud de línea actual); un test que ejecute `alembic check` contra una BD migrada de prueba; el helper `count_queries` en `tests/conftest.py`. **Preguntar antes de añadir dependencias** (ruff; mypy opcional).

## Notas

Si `alembic check` detecta divergencias existentes (p. ej. el CHECK de rol del #17 no se detecta, pero índices sí), anotarlas como fichas nuevas en vez de arreglarlas aquí.
