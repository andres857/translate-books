# 05 · Aceptación: Respuestas antiguas sobrescriben la vista actual (carreras)

Ficha: [05-carreras-en-cargas.md](05-carreras-en-cargas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con Slow 3G, tras pulsar → tres veces seguidas en «Libro», la lista de bloques corresponde a la página que indica el campo de página (comparar el número con el de la cabecera de bloques).
  - Verificado: Chrome en /admin/jobs/7 con la respuesta de bloques de la página 2 retrasada 3 s (más estricto que Slow 3G): tras → → el campo dice 3 y las claves mostradas son p003_s001–s003, también después de llegar la respuesta lenta.
- [x] Con Slow 3G, tras cambiar de libro dos veces seguidas en el Playground, los capítulos listados son los del libro seleccionado.
  - Verificado: Playground con los capítulos del libro 1 (61) retrasados 3 s: elegir libro 1 y enseguida el libro QA → «3 capítulos» y «QA PAGE ONE/TWO/THREE» en el selector, antes y después de la respuesta lenta.
- [x] En DevTools, las respuestas descartadas no producen ningún cambio de estado (sin parpadeo de contenido antiguo).
  - Verificado: muestreo cada 100 ms durante 4,5 s con el campo en 3: solo se ven bloques p003 (ningún parpadeo de p001/p002).
- [x] Con red normal, ambas vistas cargan igual que hoy.
  - Verificado: con red normal, la vista Libro navega y carga bloques (ficha 04) y el Playground carga libro, capítulos y estimación.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: navegar páginas en «Libro»; cambiar de libro y de alcance en el Playground.
  - Verificado: navegar páginas en Libro (fichas 04/05); en el Playground, cambiar de libro y elegir «Un intervalo», «Páginas sueltas» y «Libro completo» (queda marcado cada uno).
