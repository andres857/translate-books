# 06 · Aceptación: Progreso del libro: consulta cada 4 s para siempre ante un 404

Ficha: [06-polling-infinito-404.md](06-polling-infinito-404.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Abrir `/jobs/999999`: en 30 s hay exactamente 1 petición a `/api/jobs/999999` (DevTools › Network).
  - Verificado: Chrome, qa-admin en /jobs/999999: 1 petición a /api/jobs/999999 en 30 s.
- [x] La página muestra que el libro no existe y un enlace a «Libros».
  - Verificado: se ve «No encontramos ese libro · Puede que se haya eliminado o que no esté en tu lista» y el enlace «Ir a Libros».
- [x] Como `user`, abrir `/jobs/<id de otro usuario>` da el mismo resultado (1 petición, mensaje de no encontrado).
  - Verificado: qa-user en /jobs/4 (libro de qa-admin): 1 petición en 30 s y «No encontramos ese libro».
- [x] Con el api detenido, la página sigue reintentando y se recupera sola al volver el api (comportamiento actual ante errores de red).
  - Verificado: qa-user en /jobs/2 con /api/jobs/2 abortado 10 s solo en ese navegador: 3 reintentos y mensaje de error; al volver la API, la página muestra «Tu libro está listo».

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: seguir el progreso de un libro en curso hasta «Tu libro está listo».
  - Verificado: qa-user sube un PDF y /jobs/8 pasa del progreso a «Tu libro está listo» sin recargar.
