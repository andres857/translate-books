# 12 · PDFs y sesiones de base de datos que no se cierran

- **Severidad:** Medio
- **Categoría:** Robustez
- **Estado:** resuelto · commit(s) `5f7c410`
- **Ubicación:** `backend/app/api/routes_jobs.py:478` (`preview`), `backend/app/worker.py:150`, `:192`, `:250` (`SqlCache(SessionLocal())`)
- **Aceptación:** [12-recursos-sin-cerrar.aceptacion.md](12-recursos-sin-cerrar.aceptacion.md)

## Problema

- `preview` hace `pdf = pymupdf.open(path)` sin `with` ni `close()`: cada vista previa deja el archivo abierto
  hasta que el recolector lo libere (las otras rutas usan `with pymupdf.open(...)`).
- El worker crea `SqlCache(SessionLocal())` en cada trabajo y en cada recomposición y nunca cierra esa sesión (y
  su conexión SQLite).

## Cómo reproducirlo

Abrir 200 vistas previas seguidas y contar descriptores: `ls /proc/$(pgrep -f uvicorn)/fd | wc -l` crece; en el worker, contar conexiones abiertas tras varios trabajos.

## Impacto

Fugas de descriptores y conexiones en procesos de larga vida (api y worker no se reinician en semanas).

## Corrección propuesta

`with pymupdf.open(path) as pdf:` en `preview`; en el worker, crear la caché dentro de `with SessionLocal() as cs:` (o que `SqlCache` sea un context manager).

## Notas

Decisiones al resolver:

- También se cerró el `pymupdf.open(stream=...)` de la subida (`_create_job_from_bytes`), porque el primer criterio
  abarca todo `backend/app/api/*.py`. Ahora la comprobación de cifrado y el recuento de páginas van dentro del
  `with`; un fallo al leerlos da el mismo 400 «No pudimos abrir el PDF» en vez de un 500.
- En el worker se eligió `with SessionLocal() as cache_s:` alrededor de cada llamada, en lugar de convertir
  `SqlCache` en un context manager: es lo más simple y no toca `app/db/cache.py`. `close_job` (#02) no cambia.
- En CPython, el recuento de referencias ya cerraba el documento de `preview` al terminar la petición, así que los
  descriptores no crecían en la medición, ni antes ni después. La fuga real era la de las sesiones del worker
  (conexiones que quedaban prestadas en el pool). Ver la aceptación.
- `app/cli.py` (`translate` de línea de comandos) usa `SqlCache(session)` y cierra la sesión al final. Es un
  proceso corto y se deja como está.
