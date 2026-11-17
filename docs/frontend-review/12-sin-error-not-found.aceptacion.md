# 12 · Aceptación: Faltan `error.tsx` y `not-found.tsx`

Ficha: [12-sin-error-not-found.md](12-sin-error-not-found.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `ls frontend/app/error.tsx frontend/app/not-found.tsx` muestra ambos archivos.
  - Verificado: `ls frontend/app/error.tsx frontend/app/not-found.tsx` → ambos existen.
- [x] Con sesión, `http://localhost:3100/no-existe` responde 404 (`curl -s -o /dev/null -w '%{http_code}'` → `404`) y muestra un mensaje con los estilos de la app y un enlace a «Libros».
  - Verificado: Chrome con sesión de qa-admin en /no-existe → status 404, «No encontramos esta página · La dirección no existe o ya no está disponible.», enlace «Ir a Libros» (href /) y la barra lateral de la app; título «Página no encontrada · AstroBooks».
- [x] Al forzar una excepción de render (temporalmente, en desarrollo) se ve la pantalla de `error.tsx` con «Reintentar», que vuelve a renderizar la vista.
  - Verificado: excepción de render forzada sin tocar el código: /api/jobs/7 respondía `stages: null` solo en ese navegador (build de producción) → «Algo salió mal en esta vista… / Reintentar / Ir a Libros»; quitando la simulación, «Reintentar» vuelve a mostrar «Tu libro está listo».
- [x] `node ../handoff/check.mjs app lib` sigue en 0 problemas con los nuevos archivos.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0` con los dos archivos nuevos.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas (incluye /_not-found) sin errores.
- [x] Regresión de la vista afectada: navegación normal entre las vistas existentes.
  - Verificado: navegación normal por las vistas durante toda la verificación (fichas 01–10) sin pasar por error.tsx.
