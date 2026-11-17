# 07 · Aceptación: Recomponer: el bucle de espera sigue tras salir de la vista

Ficha: [07-recompose-tras-desmontar.md](07-recompose-tras-desmontar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Tras pulsar «Recomponer página» y cambiar a «Resumen» antes de que termine, no aparecen más peticiones `GET /api/jobs/<id>` desde la vista «Libro» (DevTools › Network). El sondeo de 2,5 s de la propia página sí puede seguir.
  - Verificado: Chrome en /admin/jobs/7: «Recomponer página» y a los 0,3 s pestaña «Resumen» → 0 peticiones GET /api/jobs/7 en los 8 s siguientes.
- [x] Sin salir de la vista, la recomposición sigue mostrando «Página N recompuesta…» al terminar y la imagen se actualiza.
  - Verificado: sin salir: «Página 1 recompuesta. Los archivos para Kindle se regeneran en la próxima descarga.» y la imagen cambia de src (v=1).
- [x] La consola no muestra avisos de React sobre actualizaciones de estado en un componente desmontado.
  - Verificado: consola del navegador durante toda la prueba: 0 errores y 0 avisos.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: corregir un bloque, guardar y recomponer la página.
  - Verificado: corregir un bloque, guardar y recomponer la página 1 (dos veces: con «QA» y restaurando el texto original).
