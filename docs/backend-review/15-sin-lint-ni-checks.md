# 15 · Sin linter, sin chequeo de tipos y sin control de divergencia del esquema

- **Severidad:** Medio
- **Categoría:** Herramientas
- **Estado:** resuelto · commit(s) `a9c31ed`, `6a70c3c`
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

Decisión del usuario (16-nov-2026): se añade **ruff** (`dev = ["pytest", "ruff>=0.17"]`, instalado 0.17.5 en
`backend/.venv`); **no** se añaden mypy ni pyright. Configuración en `backend/pyproject.toml`:

- `line-length = 120` (la longitud que sigue el código: 42 líneas la superan), `select = ["E", "F", "I", "B"]`.
- `Depends`, `File`, `Form`, `Query`, `Body`, `Header`, `Cookie` y `Path` de FastAPI como llamadas inmutables, para
  que `B008` no marque el patrón de dependencias de FastAPI (95 avisos falsos).
- isort: `app` propio y `alembic` externo (la carpeta `backend/alembic/` hacía que ruff lo tomara como propio).
- Reglas excluidas en todo el código, por estilo: **E501** (42 líneas > 120, casi todas prompts y f-strings que
  habría que partir a mano), **E741** (28 variables `l`, habituales en el código de maquetación) y **E731**
  (3 lambdas asignadas).
- Excluidas solo en los archivos donde ya aparecían (`per-file-ignores`): `B904`, `B905`, `B023`, `B007` y `F841`
  (24 avisos). No son mecánicos y alguno puede esconder un error, así que se revisan en la ficha nueva
  [#19](19-avisos-ruff-pendientes.md), igual que los `# noqa: BLE001` (la regla `BLE` no está activada).
- Arreglos automáticos en un commit aparte (`6a70c3c`): orden de imports (25 bloques) y 2 imports sin usar.

`alembic check` sobre una BD vacía migrada a `head` no detecta divergencias (el CHECK de rol del #17 no lo compara
Alembic). `test_alembic_check` lanza `alembic` en un subproceso con `DATABASE_URL` apuntando a una BD temporal,
porque `alembic/env.py` usa el engine de `app.db.session`, creado al importar.
