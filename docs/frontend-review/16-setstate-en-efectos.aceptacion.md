# 16 · Aceptación: setState síncrono dentro de efectos (20 casos)

Ficha: [16-setstate-en-efectos.md](16-setstate-en-efectos.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `frontend/eslint.config.mjs` ya no rebaja `react-hooks/set-state-in-effect` (la regla vuelve a su valor de `eslint-config-next`) y `npm run lint` termina con 0 errores.
  - Verificado: `frontend/eslint.config.mjs` ya no menciona `set-state-in-effect` (regla con el valor de eslint-config-next); `npx eslint .` → sin salida, código 0.
- [x] `npm run lint` no muestra avisos `react-hooks/set-state-in-effect` (`npx eslint . -f json` → 0 mensajes de esa regla).
  - Verificado: `npx eslint . -f json` → 0 mensajes de `react-hooks/set-state-in-effect` (eran 19).
- [x] No aumenta el número de `eslint-disable` (`grep -rc eslint-disable frontend/app frontend/lib`, total ≤ 12, la cifra tras el #14) ni se añade ninguno para esta regla.
  - Verificado: `grep -rc eslint-disable` → 11 (≤ 12): no se añadió ninguno y sobró el de scope-view al pasar el efecto al render.
- [x] Con red lenta (DevTools › Slow 3G), al cambiar de página en «Libro» no se ven un instante los bloques de la página anterior.
  - Verificado: Chrome en /admin/jobs/2 con la respuesta de la página 2 retrasada 3 s (más estricto que Slow 3G): muestreo cada 100 ms con el campo en 3 → solo bloques p003.
- [x] La vista «Libro» recuerda la elección Original/Comparar/Traducción tras recargar, y el Playground el tamaño de miniaturas, sin aviso de hidratación en la consola.
  - Verificado: Chrome: «Original» en la vista Libro y «Miniaturas grandes» en el Playground siguen marcados tras recargar; consola sin errores ni avisos de hidratación en Libro, Playground e historial.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `check.mjs` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` sin errores.
- [x] `cd frontend && npm run test` en verde y `npm run test:e2e` en verde (con credenciales).
  - Verificado: `npm run test` → 20 passed; `npm run test:e2e` con qa-user → 1 passed.
- [x] Regresión de la vista afectada: Libro (navegar, corregir, recomponer), Glosario, Playground completo e historial.
  - Verificado: Libro: navegar con rueda, flechas, campo e índice, borradores protegidos, corregir, guardar y recomponer; Glosario: alta, edición y borrado con y sin fallo; Playground: preparar, alcance, estimar, ejecutar, variante B, votar y PDF maquetado; historial: 3 intentos y detalle.
