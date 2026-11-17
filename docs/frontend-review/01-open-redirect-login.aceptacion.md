# 01 · Aceptación: Redirección abierta en el `?next=` del login

Ficha: [01-open-redirect-login.md](01-open-redirect-login.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con sesión iniciada desde `http://localhost:3100/login?next=/%5Cevil.example`, la URL final es `http://localhost:3100/` (DevTools › Network: ninguna petición a `evil.example`).
  - Verificado: Chrome (Playwright) en http://localhost:3100/login?next=/%5Cevil.example como qa-user → URL final `http://localhost:3100/`; 0 peticiones con host evil.example (la única coincidencia es la propia URL de /login).
- [x] `safeNext("/\\evil.example")`, `safeNext("//evil.example")`, `safeNext("https://evil.example")`, `safeNext("/\t/evil.example")` y `safeNext("javascript:alert(1)")` devuelven `"/"` (prueba unitaria en verde).
  - Verificado: `npm run test` (tests/unit/redirect.test.ts): los 10 casos de rechazo, incluidos `/\\evil.example`, `//evil.example`, `https://evil.example`, `/\t/evil.example` y `javascript:alert(1)`, devuelven `/` → 13/13 en verde.
- [x] `safeNext("/jobs/3")` devuelve `"/jobs/3"` y `safeNext("/admin/jobs/3?tab=x")` conserva la consulta (prueba unitaria).
  - Verificado: misma prueba: `/jobs/3` → `/jobs/3` y `/admin/jobs/3?tab=x` (también con `#p4`) se conservan.
- [x] `safeNext("/login")` y `safeNext("/login?next=/x")` devuelven `"/"` (sin bucle de redirección).
  - Verificado: misma prueba: `/login` y `/login?next=/x` → `/`.
- [x] Sin sesión, abrir `http://localhost:3100/jobs/3` lleva a `/login?next=%2Fjobs%2F3` y, tras entrar, a `/jobs/3`.
  - Verificado: Chrome sin sesión en /jobs/2 → `/login?next=%2Fjobs%2F2`; tras entrar como qa-user → `/jobs/2`.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0 (en cada commit de la serie).
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → `✓ Generating static pages (12/12)` y tabla de rutas, sin errores.
- [x] Regresión de la vista afectada: login → `/`, login con `?next=` interno, logout → `/login`.
  - Verificado: Chrome: login sin next → `/`; «Cerrar sesión» → `/login`; next interno → `/jobs/2`.
