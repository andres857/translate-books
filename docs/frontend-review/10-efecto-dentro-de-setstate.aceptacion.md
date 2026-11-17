# 10 · Aceptación: Efecto secundario dentro de la función de `setDisc`

Ficha: [10-efecto-dentro-de-setstate.md](10-efecto-dentro-de-setstate.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] En `next dev`, al terminar el descubrimiento del glosario hay exactamente 1 `GET /api/glossary?document_id=…` y 1 `GET /api/protected-terms?document_id=…` (DevTools › Network).
- [ ] `grep -n 'setDisc((prev)' frontend/app/admin/jobs/[id]/terms.tsx` no muestra llamadas a `load()` dentro de la función de actualización.
- [ ] Las entradas descubiertas aparecen en la lista sin recargar la página.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: descubrir el glosario de un libro y revisar las entradas automáticas.
