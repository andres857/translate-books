# 18 · Variables reutilizadas y un diccionario de locks que crece sin límite

- **Severidad:** Bajo
- **Categoría:** Estilo
- **Estado:** resuelto · commit(s) `408fdbf`
- **Ubicación:** `backend/app/api/routes_jobs.py:302` (`presign_book`), `:489` (`pages`), `:430-460` (`_epub_locks`)
- **Aceptación:** [18-estilo-menor.aceptacion.md](18-estilo-menor.aceptacion.md)

## Problema

- En `presign_book`, `p` es el `Principal` y luego se reasigna al resultado de la URL prefirmada; en `pages`, `p`
  también se reutiliza en la comprensión de lista. Funciona, pero confunde al leer el control de acceso.
- `_epub_locks` añade un `threading.Lock` por cada trabajo descargado y nunca los elimina.

## Cómo reproducirlo

Lectura del código.

## Impacto

Mantenibilidad: es fácil introducir un error de autorización al editar estas funciones.

## Corrección propuesta

Renombrar (`presigned`, `pg`) y sustituir `_epub_locks` por un lock por trabajo con limpieza (o un `WeakValueDictionary`).

## Notas

- Decisión (locks): `WeakValueDictionary` de `threading.Lock` por `(formato, trabajo)` (`_build_locks` y
  `_build_lock()` en `routes_jobs.py`) en lugar de un contador de referencias: es lo más simple y no necesita
  limpieza manual; la entrada desaparece en cuanto ninguna descarga retiene el lock (el `with` lo mantiene vivo
  mientras se genera). Un lock global (`_build_locks_guard`) protege el «get + crear», que no es atómico.
  `Lock` admite referencias débiles en el Python del proyecto (3.12, imagen `python:3.12-slim-bookworm`).
- La clave `("azw3", id)` sustituye al truco `-job.id` para separar EPUB y AZW3.
- En `job_status` (`routes_jobs.py:82`) también hay una comprensión con `p`, pero allí no hay `Principal`: fuera
  del alcance de la ficha, no se toca.
- Sin cambios en el contrato de la API: el frontend no necesita ajuste.
