# 02 · Aceptación: Enlaces a Configuración visibles para usuarios sin rol admin

Ficha: [02-enlaces-configuracion-usuario.md](02-enlaces-configuracion-usuario.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Como `user`, en «Subir un libro» (modos «Traducir» y «Solo digitalizar») no existe ningún `<a href="/admin/settings">` (DevTools › Elements, buscar `admin/settings` → 0 resultados).
  - Verificado: Chrome como qa-user, «Subir un libro»: 0 enlaces `a[href=/admin/settings]` en «Traducir» y 0 en «Solo digitalizar».
- [x] Como `user` con el método sin configurar, el aviso explica que debe avisar al administrador, sin enlace.
  - Verificado: Chrome como qa-user con /api/health simulado a translation_configured=false (solo en ese navegador): aviso «El modo de traducción aún no está listo. Avisa al administrador para que lo revise.», sin enlace.
- [x] Como `admin`, ambos enlaces siguen presentes y llevan a `/admin/settings`.
  - Verificado: Chrome como qa-admin, mismo escenario: 1 enlace en el aviso y 2 con «Solo digitalizar» (aviso + OCR); al pulsar → `/admin/settings`.
- [x] `grep -n 'admin/settings' frontend/app/components/upload-book.tsx` muestra cada aparición protegida por `isAdmin`.
  - Verificado: `grep -n admin/settings upload-book.tsx` → líneas 76 y 153, ambas dentro de `isAdmin ? … : …`.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0 (en cada commit de la serie).
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → `✓ Generating static pages (12/12)` y tabla de rutas, sin errores.
- [x] Regresión de la vista afectada: subir un PDF como `user` y como `admin` (traducir y digitalizar).
  - Verificado: Chrome con un PDF en blanco: qa-user «Traducir» (smoke test) y «Solo digitalizar» → /jobs/6; qa-admin «Traducir» → /jobs/4 y «Solo digitalizar» → /jobs/5.
