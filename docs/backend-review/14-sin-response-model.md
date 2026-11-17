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
