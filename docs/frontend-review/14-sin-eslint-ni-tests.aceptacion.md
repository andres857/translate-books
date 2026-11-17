# 14 · Aceptación: Sin ESLint ni tests: hay `eslint-disable` que no comprueba nadie

Ficha: [14-sin-eslint-ni-tests.md](14-sin-eslint-ni-tests.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `cd frontend && npm run lint` termina con 0 errores.
- [ ] Cada `eslint-disable` que queda tiene un motivo escrito en la misma línea (`grep -rn 'eslint-disable' frontend/app frontend/lib` sin líneas sin `--`).
- [ ] `npm run test` ejecuta las pruebas unitarias de `safeNext` y `routeFor` en verde.
- [ ] `npx playwright test` ejecuta el smoke test (login → subir PDF con `FAKE_TRANSLATOR` → progreso → logout) en verde contra `docker compose`.
- [ ] `.claude/skills/deploy/SKILL.md` (paso 1) incluye `npm run lint`.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: ninguna funcional: el cambio es solo de herramientas.
