# 19 · Aceptación: Tras el cambio obligatorio de contraseña no se llega a Libros

Ficha: [19-cambio-obligatorio-no-lleva-a-libros.md](19-cambio-obligatorio-no-lleva-a-libros.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Entrar con una contraseña temporal y guardar una nueva lleva a `/` con el título «Libros» y la barra lateral.
- [ ] El cambio voluntario (sesión normal, desde la barra lateral) sigue en `/change-password` y muestra «Contraseña cambiada.».
- [ ] La contraseña nueva sirve para entrar y la temporal ya no (401).

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` sin errores, `npm run lint` con 0 errores y `npm run test` en verde.
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0` y `npm run build` sin errores.
