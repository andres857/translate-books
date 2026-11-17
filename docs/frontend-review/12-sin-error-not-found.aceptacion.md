# 12 · Aceptación: Faltan `error.tsx` y `not-found.tsx`

Ficha: [12-sin-error-not-found.md](12-sin-error-not-found.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `ls frontend/app/error.tsx frontend/app/not-found.tsx` muestra ambos archivos.
- [ ] Con sesión, `http://localhost:3100/no-existe` responde 404 (`curl -s -o /dev/null -w '%{http_code}'` → `404`) y muestra un mensaje con los estilos de la app y un enlace a «Libros».
- [ ] Al forzar una excepción de render (temporalmente, en desarrollo) se ve la pantalla de `error.tsx` con «Reintentar», que vuelve a renderizar la vista.
- [ ] `node ../handoff/check.mjs app lib` sigue en 0 problemas con los nuevos archivos.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: navegación normal entre las vistas existentes.
