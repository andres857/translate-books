# 09 · Trabajo en `paused`: sin botón «Reanudar» y sondeo sin fin

- **Severidad:** Bajo
- **Categoría:** Consistencia
- **Estado:** resuelto · commit `a2b52ff` · criterios verificados en [09-estado-paused-sin-reanudar.aceptacion.md](09-estado-paused-sin-reanudar.aceptacion.md)
- **Ubicación:** `frontend/app/jobs/[id]/page.tsx:62` y `:94`
- **Aceptación:** [09-estado-paused-sin-reanudar.aceptacion.md](09-estado-paused-sin-reanudar.aceptacion.md)

## Problema

`stopped` solo cubre `cancelled` y `failed`, y el sondeo se detiene solo ante `done`/`failed`/`cancelled`. Un trabajo `paused` no tendría botón «Reanudar» y se consultaría cada 1,5 s indefinidamente.

## Cómo reproducirlo

Hoy no se puede reproducir con datos reales (ver Notas). Forzándolo en la BD de pruebas: `UPDATE jobs SET status='paused' WHERE id=<n>` y abrir `/jobs/<n>`.

## Impacto

Ninguno en la práctica actual; sería un bug en cuanto el backend use `paused` para trabajos.

## Corrección propuesta

Tratar `paused` como `stopped` (mostrar «Reanudar» y detener el sondeo), o quitar `paused` del tipo `JobStatus["status"]` si el backend nunca lo va a usar en trabajos.

## Notas

Verificado: en el backend solo las evaluaciones del Playground pasan a `paused` (`backend/app/playground.py:672`). `backend/app/worker.py:108` solo lee ese estado y `resume_job` lo acepta.
