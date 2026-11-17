# 14 · Sin ESLint ni tests: hay `eslint-disable` que no comprueba nadie

- **Severidad:** Medio
- **Categoría:** Herramientas / calidad
- **Estado:** resuelto · commit `5528cb1` · criterios verificados en [14-sin-eslint-ni-tests.aceptacion.md](14-sin-eslint-ni-tests.aceptacion.md)
- **Ubicación:** `frontend/package.json` (scripts `dev`, `build`, `start`, `typecheck`); 11 comentarios `eslint-disable`
- **Aceptación:** [14-sin-eslint-ni-tests.aceptacion.md](14-sin-eslint-ni-tests.aceptacion.md)

## Problema

No hay `eslint` ni `eslint-config-next` instalados ni script `lint`, y tampoco tests. Aun así el código tiene 11 `eslint-disable`, varios de `react-hooks/exhaustive-deps`, que ocultan dependencias que faltan. El de `frontend/app/jobs/[id]/page.tsx:74` usa `job?.status === "queued"` como dependencia, un truco frágil para reiniciar el sondeo.

## Cómo reproducirlo

`cd frontend && npm run lint` → «Missing script: lint». `grep -rn 'eslint-disable' app | wc -l` → 11.

## Impacto

Los errores de dependencias de hooks (como el #05) no se detectan, y no hay red de seguridad para los refactors #11 y #13.

## Corrección propuesta

Añadir `eslint` + `eslint-config-next` (configuración plana) y el script `lint`. Revisar cada `eslint-disable` (quitarlo si sobra, justificarlo si no). Añadir Vitest para funciones puras (`safeNext`, `routeFor`, `groupPages`) y un smoke test de Playwright: login, subir un PDF con el traductor falso, ver el progreso y cerrar sesión.

## Notas

La documentación de la versión instalada está en `frontend/node_modules/next/dist/docs/`; leerla antes de configurar ESLint (Next 16 cambió la integración de `next lint`).
