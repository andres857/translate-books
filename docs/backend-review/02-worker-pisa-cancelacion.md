# 02 · El worker puede sobrescribir una cancelación con «done», «paused» o «failed»

- **Severidad:** Alto
- **Categoría:** Concurrencia
- **Estado:** resuelto · commit(s) `f39a302`
- **Ubicación:** `backend/app/worker.py:157`, `:172`, `:204`; `backend/app/playground.py:672`, `:692`, `:701`; API en `backend/app/api/routes_jobs.py:372-378` y `routes_playground.py:402-408`
- **Aceptación:** [02-worker-pisa-cancelacion.aceptacion.md](02-worker-pisa-cancelacion.aceptacion.md)

## Problema

La API cancela con una escritura simple (`job.status = "cancelled"`), y el worker, al terminar, también escribe
sin condición:

```python
job.status, job.stage, job.progress = "done", "done", 100.0
s.commit()
```

`should_stop()` solo se consulta cada 2 s; si el usuario cancela entre la última comprobación y el commit final,
el estado vuelve a `done` (o a `failed`/`paused`). La toma de la cola ya usa el patrón correcto
(`UPDATE … WHERE status='queued'` en `claim_job`), pero el cierre no.

## Cómo reproducirlo

Test: lanzar `worker.process` con un traductor falso que, a mitad, cambie el estado a `cancelled` desde otra
sesión justo antes del commit final (o parchear `should_stop` para que devuelva `False`). Resultado actual: el job
queda en `done`. Igual con `playground.execute` y una evaluación cancelada.

## Impacto

El usuario pulsa «Detener» y el libro aparece como terminado o en error; en el Playground, una evaluación cancelada puede quedar «en pausa» y reanudarse con gasto.

## Corrección propuesta

Cerrar con una actualización condicional: `UPDATE jobs SET status='done', … WHERE id=:id AND status='running'` (y lo mismo para `failed`/`paused` y para `playground_runs`). Si no actualiza filas, registrar que fue cancelado y no tocar nada más.
