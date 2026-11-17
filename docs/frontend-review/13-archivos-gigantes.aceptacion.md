# 13 · Aceptación: Archivos con demasiadas responsabilidades

Ficha: [13-archivos-gigantes.md](13-archivos-gigantes.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Ningún archivo de `frontend/lib/` supera 300 líneas: `wc -l frontend/lib/**/*.ts*`.
  - Verificado: `find frontend/lib -name "*.ts*" | xargs wc -l` → el mayor es lib/api/playground.ts con 263 líneas (lib/api.ts, de 793, se dividió en 8 módulos + index).
- [x] `frontend/app/admin/playground/page.tsx` baja de 400 líneas y cada hook extraído vive en su archivo.
  - Verificado: app/admin/playground/page.tsx: 865 → 397 líneas; hooks en use-preparation.ts, use-run-tracking.ts y use-estimate.ts, cada uno en su archivo (más columns.tsx, controls.tsx, upload-view.tsx y mesa.tsx).
- [x] Los imports existentes `from "@/lib/api"` siguen compilando sin cambios (`tsc` sin errores).
  - Verificado: `npx tsc --noEmit` sin errores sin tocar ningún `from "@/lib/api"` (lib/api/index.ts reexporta la API pública; las 114 exportaciones de antes siguen).
- [x] No aumenta el número de `eslint-disable` (`grep -rc 'eslint-disable' frontend/app frontend/lib`, total ≤ 12; umbral actualizado: al escribirlo eran 11 y el #14, resuelto antes, dejó 12 justificadas).
  - Verificado: `grep -rc eslint-disable` → 12 tanto en 5528cb1 (antes del #13) y 1397313 (después): el refactor no añade ninguna.
- [x] El smoke test del #14 sigue en verde.
  - Verificado: `npm run test:e2e` tras desplegar → `1 passed`.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: Playground completo: subir y preparar un libro, elegir alcance, estimar, ejecutar, votar y componer.
  - Verificado: Chrome como qa-admin, Playground completo con «prueba sin API»: subir y preparar qa-pg.pdf (3 págs., 9 bloques, 3 capítulos), alcance «Un capítulo», estimación «3 bloques · ~1 llamada», ejecutar (evaluación terminada), añadir variante B, ejecutar, votar B (marcado) y PDF maquetado de A y B en la mesa (3 imágenes); sin errores de página. Repetido tras el último commit.
