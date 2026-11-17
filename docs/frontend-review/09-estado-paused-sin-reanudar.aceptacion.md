# 09 · Aceptación: Trabajo en `paused`: sin botón «Reanudar» y sondeo sin fin

Ficha: [09-estado-paused-sin-reanudar.md](09-estado-paused-sin-reanudar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con un trabajo forzado a `paused`, `/jobs/<n>` muestra el botón «Reanudar» y al pulsarlo pasa a «En cola».
- [ ] Con un trabajo `paused`, en 30 s hay como mucho 1 petición a `/api/jobs/<n>` (DevTools › Network).
- [ ] O bien: `paused` ya no forma parte del tipo de estado de trabajo y `tsc` lo confirma sin errores.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: cancelar y reanudar un trabajo desde `/jobs/<id>`.
