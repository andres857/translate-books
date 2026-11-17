# 13 · Borrado duplicado, imports internos y consultas al estilo 1.x

- **Severidad:** Medio
- **Categoría:** Estructura y mantenibilidad
- **Estado:** abierto
- **Ubicación:** `backend/app/api/routes_jobs.py:381-401` ≈ `backend/app/api/routes_playground.py:99-113`; `routes_admin.py:15` (importa `_job_or_404` privado); `db.query(` en `routes_jobs.py:330,488`, `routes_terms.py`, `worker.py:70`, `files_service.py:86`
- **Aceptación:** [13-logica-duplicada-y-legacy.aceptacion.md](13-logica-duplicada-y-legacy.aceptacion.md)

## Problema

- `delete_job` y `delete_book` repiten la comprobación de «evaluación en curso», el borrado y la limpieza de
  archivos.
- `delete_job` importa `select`, `func`, `playground` y `PlaygroundRun` **dentro** de la función.
- `routes_admin` y otras rutas importan `_job_or_404` (con guion bajo, privado) de `routes_jobs`.
- Conviven `db.query(...)` (API 1.x heredada) y `select(...)` (2.x).

## Cómo reproducirlo

`grep -rn "\.query(" backend/app` → ocurrencias en rutas, worker y servicios.

## Impacto

Cambios en una ruta de borrado que no llegan a la otra; reglas de acceso repartidas entre routers.

## Corrección propuesta

Un módulo `app/jobs_service.py` con `get_visible_job` (público), `ensure_not_busy` y `delete_job_and_files`; las dos rutas lo llaman. Pasar `db.query` a `select()`. Sin cambiar rutas ni respuestas.

## Notas

Es un refactor: no mezclar con cambios de comportamiento.
