# 07 · El flujo SSE de progreso hace consultas síncronas en el loop y no se usa

- **Severidad:** Bajo
- **Categoría:** Rendimiento (async) / código muerto
- **Estado:** abierto
- **Ubicación:** `backend/app/api/routes_jobs.py:341-369` (`job_events`)
- **Aceptación:** [07-sse-sin-uso.aceptacion.md](07-sse-sin-uso.aceptacion.md)

## Problema

`GET /api/jobs/{id}/events` es un generador `async` que, cada segundo, abre una sesión síncrona, valida la sesión
de auth y llama a `job_status` (que carga todas las páginas, #04) dentro del event loop. El frontend no lo usa:
`grep -rn "EventSource\|/events" frontend/app frontend/lib` no devuelve nada (hace polling).

## Cómo reproducirlo

`grep -rn "EventSource" frontend/app frontend/lib` → sin resultados. Abrir 20 conexiones SSE y medir la latencia de `/api/health`.

## Impacto

Superficie de API sin uso que, si alguien la abre en muchas pestañas, frena a todos.

## Corrección propuesta

Decisión pendiente (preguntar): **quitar** el endpoint (recomendado: nadie lo usa) o conservarlo moviendo la consulta a `run_in_threadpool`.
