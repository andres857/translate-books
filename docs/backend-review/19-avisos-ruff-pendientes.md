# 19 · Avisos de ruff previos silenciados por archivo

- **Severidad:** Bajo
- **Categoría:** Herramientas
- **Estado:** abierto
- **Ubicación:** `backend/pyproject.toml` (`[tool.ruff.lint.per-file-ignores]`); `app/api/routes_files.py:27,29`, `app/api/routes_jobs.py:119`, `app/pipeline/analyze.py`, `curved.py`, `digitize.py`, `fonts.py:204`, `ocr.py:183,215`, `translate.py:754`, `app/playground.py:271,662`, `tests/test_admin.py:90`
- **Aceptación:** [19-avisos-ruff-pendientes.aceptacion.md](19-avisos-ruff-pendientes.aceptacion.md)

## Problema

Al activar ruff (#15) quedaron 24 avisos de `B`/`F` del código previo que no se pueden arreglar de forma mecánica
y que se silenciaron por archivo para que `ruff check app tests` pase:

- `B904` (3): `raise HTTPException(...)` dentro de `except` sin `from err` / `from None`.
- `B905` (11): `zip()` sin `strict=`; si las listas no miden lo mismo se trunca en silencio.
- `B023` (5): funciones internas que leen variables del bucle (`run`, `run_style` en `analyze.py`; `saved` en
  `playground.py`). Parecen usarse dentro de la misma iteración, pero hay que confirmarlo.
- `B007` (3): variables de bucle sin usar (`ext`, `key`, `height`).
- `F841` (2): variables asignadas sin usar en `ocr.py` (`upper`, `doc`).

Además hay 39 `# noqa: BLE001` que ningún linter comprueba (la regla `BLE` no está activada); con `BLE` y `RUF100`
ruff marca 17 de ellos como innecesarios y un `except Exception` sin comentario.

## Cómo reproducirlo

`cd backend && .venv/bin/ruff check app tests --no-cache --config 'lint.per-file-ignores = {}'` → 24 avisos.
`.venv/bin/ruff check app tests --extend-select BLE,RUF100` → 18 avisos.

## Impacto

Los archivos con silencio por archivo no avisan de casos nuevos de esas reglas; un `zip` o un cierre sobre la
variable del bucle mal hecho pasaría sin aviso.

## Corrección propuesta

Revisar cada aviso a mano (`strict=True` donde las longitudes deben coincidir, `from None` en los `HTTPException`,
fijar las variables del bucle como argumento por defecto, quitar las variables sin usar), quitar las entradas de
`per-file-ignores` y decidir si se activa `BLE` (+`RUF100`) para que los `# noqa: BLE001` signifiquen algo.

## Notas

Detectado al cerrar el #15; no se arregla allí porque no son cambios mecánicos.
