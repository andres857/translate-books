# 04 · Aceptación: Vista Libro: cambiar de página descarta las correcciones sin guardar

Ficha: [04-compare-descarta-borradores.md](04-compare-descarta-borradores.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con un borrador sin guardar, girar la rueda hasta el borde no cambia de página y se avisa de que hay cambios sin guardar.
  - Verificado: Chrome, qa-admin en /admin/jobs/7 (libro QA de 3 págs.): con un borrador, la rueda sobre la hoja en el borde deja el campo en 1 y aparece el aviso «Tienes correcciones sin guardar…» (1 alerta).
- [x] Con un borrador sin guardar, pulsar → (con el foco fuera del campo) no cambia de página.
  - Verificado: con el borrador y el foco en el título, → deja el campo en 1.
- [x] Con un borrador sin guardar, elegir otra página en el índice pide confirmación; «Cancelar» mantiene la página y el texto.
  - Verificado: con el borrador, «Página 2» del índice abre «Tienes correcciones sin guardar en esta página. ¿Cambiar de página y descartarlas?»; con Cancelar sigue en 1 y el texto conserva «(QA)».
- [x] Sin borradores, rueda, flechas, campo e índice cambian de página como hoy.
  - Verificado: sin borradores: rueda → 2, ← → 1, campo «3» + Enter → 3, índice «Página 1» → 1.
- [x] Tras «Guardar», la navegación vuelve a ser libre.
  - Verificado: tras «Guardar», la rueda pasa a la página 2. Después se restauró el texto original del bloque.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: navegar el libro con rueda, flechas e índice; corregir, guardar y recomponer una página.
  - Verificado: navegación con rueda, flechas, campo e índice (arriba); corregir, guardar y recomponer la página 1 → «Página 1 recompuesta…» (verificación de la ficha 07).
