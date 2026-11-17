# 05 · Aceptación: Respuestas antiguas sobrescriben la vista actual (carreras)

Ficha: [05-carreras-en-cargas.md](05-carreras-en-cargas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con Slow 3G, tras pulsar → tres veces seguidas en «Libro», la lista de bloques corresponde a la página que indica el campo de página (comparar el número con el de la cabecera de bloques).
- [ ] Con Slow 3G, tras cambiar de libro dos veces seguidas en el Playground, los capítulos listados son los del libro seleccionado.
- [ ] En DevTools, las respuestas descartadas no producen ningún cambio de estado (sin parpadeo de contenido antiguo).
- [ ] Con red normal, ambas vistas cargan igual que hoy.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: navegar páginas en «Libro»; cambiar de libro y de alcance en el Playground.
