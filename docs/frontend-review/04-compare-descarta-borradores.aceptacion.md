# 04 · Aceptación: Vista Libro: cambiar de página descarta las correcciones sin guardar

Ficha: [04-compare-descarta-borradores.md](04-compare-descarta-borradores.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con un borrador sin guardar, girar la rueda hasta el borde no cambia de página y se avisa de que hay cambios sin guardar.
- [ ] Con un borrador sin guardar, pulsar → (con el foco fuera del campo) no cambia de página.
- [ ] Con un borrador sin guardar, elegir otra página en el índice pide confirmación; «Cancelar» mantiene la página y el texto.
- [ ] Sin borradores, rueda, flechas, campo e índice cambian de página como hoy.
- [ ] Tras «Guardar», la navegación vuelve a ser libre.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: navegar el libro con rueda, flechas e índice; corregir, guardar y recomponer una página.
