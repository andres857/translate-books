# 13 · Aceptación: Archivos con demasiadas responsabilidades

Ficha: [13-archivos-gigantes.md](13-archivos-gigantes.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Ningún archivo de `frontend/lib/` supera 300 líneas: `wc -l frontend/lib/**/*.ts*`.
- [ ] `frontend/app/admin/playground/page.tsx` baja de 400 líneas y cada hook extraído vive en su archivo.
- [ ] Los imports existentes `from "@/lib/api"` siguen compilando sin cambios (`tsc` sin errores).
- [ ] No aumenta el número de `eslint-disable` (`grep -rc 'eslint-disable' frontend/app frontend/lib`, total ≤ 11).
- [ ] El smoke test del #14 sigue en verde.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: Playground completo: subir y preparar un libro, elegir alcance, estimar, ejecutar, votar y componer.
