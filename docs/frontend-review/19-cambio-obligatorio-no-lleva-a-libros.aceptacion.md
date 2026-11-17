# 19 · Aceptación: Tras el cambio obligatorio de contraseña no se llega a Libros

Ficha: [19-cambio-obligatorio-no-lleva-a-libros.md](19-cambio-obligatorio-no-lleva-a-libros.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Entrar con una contraseña temporal y guardar una nueva lleva a `/` con el título «Libros» y la barra lateral.
  - Verificado: Chrome: admin genera una temporal para qa-user; qa-user entra con ella → /change-password; guarda una nueva → `/`, h1 «Libros» y barra lateral.
- [x] El cambio voluntario (sesión normal, desde la barra lateral) sigue en `/change-password` y muestra «Contraseña cambiada.».
  - Verificado: desde la barra lateral «Cambiar contraseña», con sesión normal: se queda en /change-password y muestra «Contraseña cambiada.».
- [x] La contraseña nueva sirve para entrar y la temporal ya no (401).
  - Verificado: POST /api/auth/login con la nueva → 200; con la temporal → 401.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` sin errores, `npm run lint` con 0 errores y `npm run test` en verde.
  - Verificado: `npx tsc --noEmit` sin salida; `npm run lint` código 0 (0 errores); `npm run test` → 17 passed.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0` y `npm run build` sin errores.
  - Verificado: `check.mjs` → `Problemas: 0`; `npm run build` sin errores.
