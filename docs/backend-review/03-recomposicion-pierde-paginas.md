# 03 · Pedir otra recomposición mientras se recompone pierde la petición

- **Severidad:** Medio
- **Categoría:** Concurrencia
- **Estado:** abierto
- **Ubicación:** `backend/app/api/routes_admin.py:138-153` (`recompose`) frente a `backend/app/worker.py:178-205` (`process_recompose`)
- **Aceptación:** [03-recomposicion-pierde-paginas.aceptacion.md](03-recomposicion-pierde-paginas.aceptacion.md)

## Problema

La API añade la página a `job.options["recompose"]` y pone el job en `queued`. El worker trabaja con una copia de
`options` leída al empezar y al final hace `options.pop("recompose")` y `job.options = options`: lo que la API
añadió mientras tanto se sobrescribe y el job queda `done`.

## Cómo reproducirlo

1. Pedir recomponer la página 3; mientras el worker la procesa, pedir la página 5.
2. Al terminar: `options` ya no tiene `recompose`, el job está `done` y la página 5 no se recompuso.

## Impacto

El admin cree que pidió dos recomposiciones y solo se hizo una; no hay error ni aviso.

## Corrección propuesta

Decisión pendiente (preguntar): **(a)** responder 409 mientras el job esté `queued`/`running` con una recomposición, o **(b)** al terminar, releer `options` de la BD y quitar solo las páginas hechas, dejando el job en `queued` si quedan otras. (a) es más simple y coherente con #01.
