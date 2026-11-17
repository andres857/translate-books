# 16 · Aceptación: setState síncrono dentro de efectos (20 casos)

Ficha: [16-setstate-en-efectos.md](16-setstate-en-efectos.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `frontend/eslint.config.mjs` ya no rebaja `react-hooks/set-state-in-effect` (la regla vuelve a su valor de `eslint-config-next`) y `npm run lint` termina con 0 errores.
- [ ] `npm run lint` no muestra avisos `react-hooks/set-state-in-effect` (`npx eslint . -f json` → 0 mensajes de esa regla).
- [ ] No aumenta el número de `eslint-disable` (`grep -rc eslint-disable frontend/app frontend/lib`, total ≤ 9) ni se añade ninguno para esta regla.
- [ ] Con red lenta (DevTools › Slow 3G), al cambiar de página en «Libro» no se ven un instante los bloques de la página anterior.
- [ ] La vista «Libro» recuerda la elección Original/Comparar/Traducción tras recargar, y el Playground el tamaño de miniaturas, sin aviso de hidratación en la consola.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] `cd frontend && npm run test` en verde y `npm run test:e2e` en verde (con credenciales).
- [ ] Regresión de la vista afectada: Libro (navegar, corregir, recomponer), Glosario, Playground completo e historial.
