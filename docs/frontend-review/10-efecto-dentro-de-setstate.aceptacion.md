# 10 · Aceptación: Efecto secundario dentro de la función de `setDisc`

Ficha: [10-efecto-dentro-de-setstate.md](10-efecto-dentro-de-setstate.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] En `next dev`, al terminar el descubrimiento del glosario hay exactamente 1 `GET /api/glossary?document_id=…` y 1 `GET /api/protected-terms?document_id=…` (DevTools › Network).
  - Verificado: `next dev` (StrictMode) en :3100 con el contenedor del frontend parado durante la prueba: «Generar glosario» en /admin/jobs/7; al terminar (8 s), exactamente 1 GET /api/glossary y 1 GET /api/protected-terms.
- [x] `grep -n 'setDisc((prev)' frontend/app/admin/jobs/[id]/terms.tsx` no muestra llamadas a `load()` dentro de la función de actualización.
  - Verificado: `grep -n "setDisc((prev)" terms.tsx` → 0 coincidencias (la recarga está en un efecto que compara el estado anterior).
- [x] Las entradas descubiertas aparecen en la lista sin recargar la página.
  - Verificado: sin recargar la página, la tabla muestra la entrada descubierta «QA PAGE → rótulo página de control de calidad» (origen auto) tras la recarga automática.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: descubrir el glosario de un libro y revisar las entradas automáticas.
  - Verificado: descubrir el glosario del libro QA y revisar la entrada automática en la tabla.
