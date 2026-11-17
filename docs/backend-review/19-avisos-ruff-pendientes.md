# 19 · Avisos de ruff previos silenciados por archivo

- **Severidad:** Bajo
- **Categoría:** Herramientas
- **Estado:** resuelto · commit(s) `26b9542`, `8f0a64c`
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

- Decisión (B904): `from e` en `FileValidationError` (es el error de negocio que se muestra) y `from None` en
  `FileNotFound` y en el PDF que PyMuPDF no abre (el detalle interno no aporta). Solo cambia el encadenamiento
  del traceback; código y texto de las respuestas HTTP son los mismos.
- Decisión (B905): `strict=True` solo donde las longitudes coinciden por construcción o ya se comprueban:
  `zip(para, kinds)` y `zip(segments, paragraphs)` en `analyze.py` (una entrada por párrafo, sin `continue`),
  `zip(chain, chain[1:] + [None])` en `curved.py`, `zip(group, parts)` en `translate.py` (tras
  `len(parts) == len(group)`) y `zip(before, after)` en `tests/test_admin.py` (tras el assert de longitud).
  `strict=False` en los pares consecutivos `zip(x, x[1:])` (miden distinto a propósito) y en
  `zip(run.variants, run.results)` de `playground.py` (una evaluación en curso tiene menos resultados).
- Decisión (B023): los 5 avisos son falsos positivos y quedan con `# noqa: B023` y su motivo. `flush()` en
  `_runs_html` se llama dentro de la misma iteración y debe ver los valores *actuales* de `run`/`run_style`
  (que el bucle interno reasigna): fijarlos como argumento por defecto cambiaría el resultado. `tick()` en
  `playground.py` se pasa a `run_variant`, que lo llama de forma síncrona en la misma iteración.
- B007/F841: `_ext`, `_height`, `joint.values()` en lugar de `.items()`; se quitan `letters`/`upper` y `doc`
  de `ocr.py` (cálculos sin efectos; `_erase_in_image` obtiene su propio `page.parent`).
- Decisión (BLE): se activan `BLE` y `RUF100`. Ruff quitó 15 `# noqa: BLE001` innecesarios (esos `except`
  registran con `log.exception`/`exc_info` o relanzan) y los noqa sin efecto `F401` (`import pymupdf.layout`) y
  `E731` (regla ya ignorada); los comentarios explicativos se conservan. El `except Exception` al abrir el PDF
  subido (`routes_jobs.py`) lleva `# noqa: BLE001` con motivo: cualquier fallo de PyMuPDF debe dar un 400.
  Quedan 25 `# noqa: BLE001`, todos comprobados por RUF100.
- Sin cambios en el contrato de la API: el frontend no necesita ajuste.
