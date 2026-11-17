# 03 · Pedir otra recomposición mientras se recompone pierde la petición

- **Severidad:** Medio
- **Categoría:** Concurrencia
- **Estado:** resuelto · commit(s) `30a919f`
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

## Notas

Decisión del usuario (16-nov-2026): opción **(a)**. `POST /api/admin/jobs/{id}/pages/{n}/recompose` responde 409
(«Ya se está recomponiendo una página de este libro: espera a que termine.») cuando el job está en `queued` o
`running` con una recomposición pedida; no se encolan páginas. Al implementarlo se vio que el endpoint ya daba 409
en esos estados (por `status != "done"`, con el mensaje «tiene que estar terminado»), así que el hueco real era la
carrera entre dos peticiones que leen «done» a la vez: el paso a `queued` es ahora un `UPDATE … WHERE status='done'`
y, si no aplica, responde el mismo 409. El frontend no cambia: `compare.tsx` muestra el `detail` del error.
