# 06 · Aceptación: Progreso del libro: consulta cada 4 s para siempre ante un 404

Ficha: [06-polling-infinito-404.md](06-polling-infinito-404.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Abrir `/jobs/999999`: en 30 s hay exactamente 1 petición a `/api/jobs/999999` (DevTools › Network).
- [ ] La página muestra que el libro no existe y un enlace a «Libros».
- [ ] Como `user`, abrir `/jobs/<id de otro usuario>` da el mismo resultado (1 petición, mensaje de no encontrado).
- [ ] Con el api detenido, la página sigue reintentando y se recupera sola al volver el api (comportamiento actual ante errores de red).

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: seguir el progreso de un libro en curso hasta «Tu libro está listo».
