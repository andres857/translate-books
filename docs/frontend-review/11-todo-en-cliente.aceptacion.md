# 11 · Aceptación: Todas las páginas son de cliente: el HTML del servidor solo trae «Cargando…»

Ficha: [11-todo-en-cliente.md](11-todo-en-cliente.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con sesión válida, `curl -s -b '<cookie de sesión>' http://localhost:3100/` contiene el nombre del usuario (`grep -c '<nombre>'` ≥ 1): la sesión se resuelve en el servidor.
  - Verificado: HTML de / pedido con la cookie de qa-user → contiene «QA user» 2 veces (barra lateral), sin `auth-screen`: la sesión se resuelve en el servidor (lib/server/session.ts).
- [x] Recargar `/` con sesión no muestra la pantalla «Cargando…» del `AppShell` (grabación de rendimiento de DevTools: el primer pintado ya incluye la barra lateral).
  - Verificado: Chrome, recarga de / con sesión: en DOMContentLoaded (antes de hidratar) ya hay `nav.sidenav` y 0 `.auth-screen`; consola sin errores.
- [x] Al menos `/admin/users` y `/admin/settings` son Server Components: `grep -L '"use client"' frontend/app/admin/users/page.tsx frontend/app/admin/settings/page.tsx` lista ambos.
  - Verificado: `grep -L "use client" frontend/app/admin/users/page.tsx frontend/app/admin/settings/page.tsx` → lista ambos; el HTML servido de /admin/users ya trae qa-user@astrobooks.local y el de /admin/settings el modelo, sin «Cargando configuración…».
- [x] Sin sesión, `/` sigue redirigiendo a `/login` (307) y el login funciona igual.
  - Verificado: `curl -sI localhost:3100/` sin cookie → `307` con `location: /login`; el login funciona (smoke test `1 passed`).
- [x] La CSP con nonce sigue presente: `curl -sI localhost:3100/login | grep -c nonce-` → `1`.
  - Verificado: `curl -sI localhost:3100/login | grep -c nonce-` → `1`.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: recorrido completo de la lista de comportamientos de la revisión (login, libros, subida, progreso, administración).
  - Verificado: Chrome: las 10 rutas como qa-admin y 4 como qa-user sin errores de consola ni de hidratación (el único es el 404 propio de /no-existe; /admin/users como user → /); smoke test (login, subida, progreso, logout); guardar Configuración; en Usuarios cambiar rol con reautenticación y volver; Playground completo (ficha 13).
