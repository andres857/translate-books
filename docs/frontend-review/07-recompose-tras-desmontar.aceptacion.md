# 07 · Aceptación: Recomponer: el bucle de espera sigue tras salir de la vista

Ficha: [07-recompose-tras-desmontar.md](07-recompose-tras-desmontar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Tras pulsar «Recomponer página» y cambiar a «Resumen» antes de que termine, no aparecen más peticiones `GET /api/jobs/<id>` desde la vista «Libro» (DevTools › Network). El sondeo de 2,5 s de la propia página sí puede seguir.
- [ ] Sin salir de la vista, la recomposición sigue mostrando «Página N recompuesta…» al terminar y la imagen se actualiza.
- [ ] La consola no muestra avisos de React sobre actualizaciones de estado en un componente desmontado.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: corregir un bloque, guardar y recomponer la página.
