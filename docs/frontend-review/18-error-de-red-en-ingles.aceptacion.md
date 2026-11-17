# 18 · Aceptación: Un fallo de red muestra «Failed to fetch» en inglés

Ficha: [18-error-de-red-en-ingles.md](18-error-de-red-en-ingles.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con las escrituras a `/api/glossary` abortadas en el navegador, el aviso dice «No hay conexión con el servidor…» (no «Failed to fetch»).
- [ ] En `/jobs/<id>` con `/api/jobs/<id>` abortado, el aviso dice lo mismo y la página sigue reintentando (comportamiento del #06).
- [ ] Prueba unitaria: `apiFetch` con un `fetch` que rechaza lanza `ApiError` con `status` 0 y el mensaje en español.
- [ ] `grep -rn "Failed to fetch" frontend/app frontend/lib` → sin resultados.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && npm run lint` con 0 errores y `npm run test` en verde.
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
