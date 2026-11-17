# 14 · Ningún endpoint declara su esquema de respuesta

- **Severidad:** Medio
- **Categoría:** Contrato de la API
- **Estado:** abierto
- **Ubicación:** Todos los routers de `backend/app/api/` (p. ej. `routes_jobs.py:158-195` `job_status`, `routes_settings.py:376`, `auth/users.py` `public`)
- **Aceptación:** [14-sin-response-model.aceptacion.md](14-sin-response-model.aceptacion.md)

## Problema

Las respuestas se arman como `dict` a mano; ninguna ruta tiene `response_model` ni tipo de retorno. FastAPI no
filtra la salida (un campo añadido por error a un dict sale tal cual) y el OpenAPI no describe las respuestas.

## Cómo reproducirlo

`curl -s localhost:8000/openapi.json | jq '.paths["/api/jobs/{job_id}"].get.responses["200"]'` → esquema vacío.

## Impacto

Sin contrato verificable, un cambio en un dict puede exponer datos o romper el frontend sin que ningún test lo note.

## Corrección propuesta

Esquemas Pydantic `JobRead`, `JobStage`, `SettingsPublic`/`SettingsUserView`, `UserRead`, etc., como `response_model` en las rutas usadas por el rol user (jobs, settings, auth, users). El JSON no debe cambiar: comparar las respuestas antes y después.

## Notas

Empezar por las rutas del rol user; el Playground (admin) puede quedar para después y anotarse.

Plan (decidido por el coordinador con la autorización del usuario, 17-nov-2026; es un cambio de estructura, no de
contrato):

- Alcance: las rutas que devuelven JSON de `routes_jobs.py`, `routes_settings.py` (las dos vistas de
  `GET /api/settings`: la completa del admin, `RuntimeSettings.public()`, y la del user de #08,
  `RuntimeSettings.method()`), `routes_auth.py` y `routes_users.py`.
- Esquemas Pydantic en un módulo nuevo `backend/app/api/schemas.py`, usados como `response_model`; las funciones
  siguen devolviendo dicts y FastAPI los valida y filtra.
- El JSON no cambia: antes de tocar el código se guardan snapshots (JSON) de `GET /api/jobs`, `/api/jobs/{id}`,
  `/api/auth/me`, `/api/settings` (admin y user) y `/api/users` generados con el cliente de test, y un test los
  compara byte a byte con la respuesta tras el cambio (los valores variables —ids, correos, token CSRF, totales—
  se sustituyen por marcadores antes de comparar). Sin `exclude_none`: un campo `None` sigue saliendo como
  `null`, y no se añaden campos opcionales que hoy no salen.
- Las rutas que devuelven archivos, PNG o streaming (`download`, `report`, `preview`, `events`) no llevan
  `response_model`.
- No es un cambio de contrato: el frontend no se toca.
- Fuera de alcance (siguiente paso, sin ficha nueva): `routes_playground.py`, `routes_admin.py` y el resto de
  routers (`routes_terms.py`, `routes_files.py`).
