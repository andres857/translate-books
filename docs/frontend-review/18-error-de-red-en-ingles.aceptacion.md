# 18 · Aceptación: Un fallo de red muestra «Failed to fetch» en inglés

Ficha: [18-error-de-red-en-ingles.md](18-error-de-red-en-ingles.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con las escrituras a `/api/glossary` abortadas en el navegador, el aviso dice «No hay conexión con el servidor…» (no «Failed to fetch»).
  - Verificado: Chrome como qa-admin en /admin/jobs/7 › Glosario con las escrituras a /api/glossary abortadas: «No hay conexión con el servidor. Comprueba que el servicio esté en marcha e inténtalo de nuevo.».
- [x] En `/jobs/<id>` con `/api/jobs/<id>` abortado, el aviso dice lo mismo y la página sigue reintentando (comportamiento del #06).
  - Verificado: qa-user en /jobs/2 con /api/jobs/2 abortado 9 s: el mismo mensaje, 4 reintentos, y al volver la API «Tu libro está listo».
- [x] Prueba unitaria: `apiFetch` con un `fetch` que rechaza lanza `ApiError` con `status` 0 y el mensaje en español.
  - Verificado: tests/unit/api-fetch.test.ts: fetch rechazado → ApiError con status 0, code NETWORK y el mensaje en español; AbortError se deja pasar; encabezados correctos → 3/3 en verde.
- [x] `grep -rn "Failed to fetch" frontend/app frontend/lib` → sin resultados.
  - Verificado: `grep -rn "Failed to fetch" frontend/app frontend/lib` → sin resultados.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` sin salida, código 0.
- [x] `cd frontend && npm run lint` con 0 errores y `npm run test` en verde.
  - Verificado: `npm run lint` código 0 (0 errores) y `npm run test` → 20 passed.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `check.mjs` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` sin errores.
