# 12 · PDFs y sesiones de base de datos que no se cierran

- **Severidad:** Medio
- **Categoría:** Robustez
- **Estado:** abierto
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
