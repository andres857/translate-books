# 09 · Aceptación: Trabajo en `paused`: sin botón «Reanudar» y sondeo sin fin

Ficha: [09-estado-paused-sin-reanudar.md](09-estado-paused-sin-reanudar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con un trabajo forzado a `paused`, `/jobs/<n>` muestra el botón «Reanudar» y al pulsarlo pasa a «En cola».
  - Verificado: job 3 de qa-user puesto en `paused` en la BD; /jobs/3 muestra «El proceso está en pausa.» y «Reanudar»; al pulsarlo → «Tu libro está en la cola y comenzará en breve.» y termina en «Tu libro está listo».
- [x] Con un trabajo `paused`, en 30 s hay como mucho 1 petición a `/api/jobs/<n>` (DevTools › Network).
  - Verificado: con el job 3 en pausa, 1 petición a /api/jobs/3 en 30 s.
- [x] O bien: `paused` ya no forma parte del tipo de estado de trabajo y `tsc` lo confirma sin errores.
  - Verificado: alternativa no elegida: se cumple la primera (criterios 1 y 2), así que `paused` sigue en el tipo; `npx tsc --noEmit` sin errores.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: cancelar y reanudar un trabajo desde `/jobs/<id>`.
  - Verificado: job 2 de qa-user en «running»: «Cancelar» → «El proceso fue cancelado…»; «Reanudar» → en cola → «Tu libro está listo».
