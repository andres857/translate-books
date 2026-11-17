# 04 · El estado de un trabajo carga todas sus páginas y el listado hace N+1

- **Severidad:** Alto
- **Categoría:** Rendimiento
- **Estado:** abierto
- **Ubicación:** `backend/app/api/routes_jobs.py:158-195` (`job_status`, línea 176) y `:328-333` (`list_jobs`)
- **Aceptación:** [04-job-status-carga-paginas.aceptacion.md](04-job-status-carga-paginas.aceptacion.md)

## Problema

`job_status` calcula `review_pages` recorriendo `job.pages` (carga perezosa de **todas** las páginas) y lee
`job.document` (otra carga). Se llama en `GET /api/jobs/{id}`, que el frontend consulta cada 1,5 s mientras hay un
libro en proceso, y una vez por trabajo en `GET /api/jobs` (hasta 50).

## Cómo reproducirlo

Medido sobre una copia de la BD real (1 libro de 192 páginas), contando `before_cursor_execute`:

- `GET /api/jobs/1`: 5 queries, una de ellas trae las 192 filas de `pages` con su JSON.
- `GET /api/jobs`: 5 queries con 1 trabajo; crece **2 por trabajo** (document + pages): ~103 con 50.

(Las 3 primeras queries son de la sesión: buscar sesión, usuario y `last_seen`.)

## Impacto

Cada sondeo lee el libro entero; con libros grandes y varios usuarios el polling satura SQLite (un solo escritor, el worker, compite con esas lecturas).

## Corrección propuesta

Obtener las páginas a revisar con una consulta que filtre `Page.needs_review` y devuelva solo `number` y `review_reasons`; en `list_jobs`, `options(joinedload(Job.document))` y las páginas a revisar agrupadas en una sola consulta `IN (...)`. El JSON de respuesta no cambia.

## Notas

Usar el helper `count_queries` que añade el #15 (si aún no existe, crearlo en `tests/conftest.py` en este commit).
