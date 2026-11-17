# 07 · El flujo SSE de progreso hace consultas síncronas en el loop y no se usa

- **Severidad:** Bajo
- **Categoría:** Rendimiento (async) / código muerto
- **Estado:** resuelto · commit(s) `69ae2c7`
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

## Notas

Decisión del usuario (17-nov-2026): **quitar** el endpoint `GET /api/jobs/{id}/events` en lugar de conservarlo con
`run_in_threadpool`. Motivo: nadie lo usa (el frontend hace polling a `GET /api/jobs/{id}`, que no cambia) y así
desaparece la superficie que bloqueaba el event loop. Es un cambio de contrato (la ruta ahora da 404), indicado en el
commit; el frontend no necesita ajuste porque no la referencia. Se quitaron con ella los imports sin uso
(`asyncio`, `json`, `StreamingResponse`, `SessionLocal`, `auth_sessions`, `AuthSession`), el test del flujo SSE
(`test_events_stream_stops_when_session_is_revoked`) y sus entradas en la matriz de autorización y en `NOT_JSON`.
Se añadió `test_events_endpoint_was_removed` (404/405 y ausente del OpenAPI): es el único test que nombra la ruta, y
solo para comprobar que ya no existe; el grep del criterio (`backend/app`, `frontend/app`, `frontend/lib`) queda vacío.
