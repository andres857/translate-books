# 11 · Aceptación: Todas las páginas son de cliente: el HTML del servidor solo trae «Cargando…»

Ficha: [11-todo-en-cliente.md](11-todo-en-cliente.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con sesión válida, `curl -s -b '<cookie de sesión>' http://localhost:3100/` contiene el nombre del usuario (`grep -c '<nombre>'` ≥ 1): la sesión se resuelve en el servidor.
- [ ] Recargar `/` con sesión no muestra la pantalla «Cargando…» del `AppShell` (grabación de rendimiento de DevTools: el primer pintado ya incluye la barra lateral).
- [ ] Al menos `/admin/users` y `/admin/settings` son Server Components: `grep -L '"use client"' frontend/app/admin/users/page.tsx frontend/app/admin/settings/page.tsx` lista ambos.
- [ ] Sin sesión, `/` sigue redirigiendo a `/login` (307) y el login funciona igual.
- [ ] La CSP con nonce sigue presente: `curl -sI localhost:3100/login | grep -c nonce-` → `1`.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: recorrido completo de la lista de comportamientos de la revisión (login, libros, subida, progreso, administración).
