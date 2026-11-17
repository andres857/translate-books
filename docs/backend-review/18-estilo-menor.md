# 18 · Variables reutilizadas y un diccionario de locks que crece sin límite

- **Severidad:** Bajo
- **Categoría:** Estilo
- **Estado:** abierto
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
