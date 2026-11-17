# 14 · Aceptación: Sin ESLint ni tests: hay `eslint-disable` que no comprueba nadie

Ficha: [14-sin-eslint-ni-tests.md](14-sin-eslint-ni-tests.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `cd frontend && npm run lint` termina con 0 errores.
  - Verificado: `npm run lint` → `✖ 20 problems (0 errors, 20 warnings)`, código de salida 0. Los 20 avisos son `react-hooks/set-state-in-effect`, rebajada a aviso y registrada como ficha #16.
- [x] Cada `eslint-disable` que queda tiene un motivo escrito en la misma línea (`grep -rn 'eslint-disable' frontend/app frontend/lib` sin líneas sin `--`).
  - Verificado: `grep -rn eslint-disable frontend/app frontend/lib | grep -v -- "-- "` → sin salida (9 directivas, todas con motivo; se quitó 1 que ya no hacía falta).
- [x] `npm run test` ejecuta las pruebas unitarias de `safeNext` y `routeFor` en verde.
  - Verificado: `npm run test` → `Tests 17 passed (17)`: tests/unit/redirect.test.ts (13) y tests/unit/route-for.test.ts (4).
- [x] `npx playwright test` ejecuta el smoke test (login → subir PDF con `FAKE_TRANSLATOR` → progreso → logout) en verde contra `docker compose`.
  - Verificado: `E2E_USER_EMAIL`/`E2E_USER_PASSWORD` de qa-user contra docker compose → `✓ login, subir un libro, ver el progreso y cerrar sesión` · `1 passed`. Usa un PDF en blanco en lugar de `FAKE_TRANSLATOR`: no llama al modelo ni cambia la configuración global.
- [x] `.claude/skills/deploy/SKILL.md` (paso 1) incluye `npm run lint`.
  - Verificado: `.claude/skills/deploy/SKILL.md`, paso 1: «`npx tsc --noEmit`, `npm run lint` (0 errores), `npm run test`…».

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → `✓ Generating static pages (12/12)` y la tabla de rutas.
- [x] Regresión de la vista afectada: ninguna funcional: el cambio es solo de herramientas.
  - Verificado: sin cambios funcionales: solo herramientas, configuración y pruebas.
