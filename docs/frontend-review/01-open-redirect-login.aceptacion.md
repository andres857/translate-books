# 01 · Aceptación: Redirección abierta en el `?next=` del login

Ficha: [01-open-redirect-login.md](01-open-redirect-login.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con sesión iniciada desde `http://localhost:3100/login?next=/%5Cevil.example`, la URL final es `http://localhost:3100/` (DevTools › Network: ninguna petición a `evil.example`).
- [ ] `safeNext("/\\evil.example")`, `safeNext("//evil.example")`, `safeNext("https://evil.example")`, `safeNext("/\t/evil.example")` y `safeNext("javascript:alert(1)")` devuelven `"/"` (prueba unitaria en verde).
- [ ] `safeNext("/jobs/3")` devuelve `"/jobs/3"` y `safeNext("/admin/jobs/3?tab=x")` conserva la consulta (prueba unitaria).
- [ ] `safeNext("/login")` y `safeNext("/login?next=/x")` devuelven `"/"` (sin bucle de redirección).
- [ ] Sin sesión, abrir `http://localhost:3100/jobs/3` lleva a `/login?next=%2Fjobs%2F3` y, tras entrar, a `/jobs/3`.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: login → `/`, login con `?next=` interno, logout → `/login`.
