# 02 · Aceptación: Enlaces a Configuración visibles para usuarios sin rol admin

Ficha: [02-enlaces-configuracion-usuario.md](02-enlaces-configuracion-usuario.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Como `user`, en «Subir un libro» (modos «Traducir» y «Solo digitalizar») no existe ningún `<a href="/admin/settings">` (DevTools › Elements, buscar `admin/settings` → 0 resultados).
- [ ] Como `user` con el método sin configurar, el aviso explica que debe avisar al administrador, sin enlace.
- [ ] Como `admin`, ambos enlaces siguen presentes y llevan a `/admin/settings`.
- [ ] `grep -n 'admin/settings' frontend/app/components/upload-book.tsx` muestra cada aparición protegida por `isAdmin`.

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: subir un PDF como `user` y como `admin` (traducir y digitalizar).
