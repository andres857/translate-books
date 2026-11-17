# 15 · Aceptación: Todas las pestañas del navegador tienen el mismo título

Ficha: [15-titulos-por-pagina.md](15-titulos-por-pagina.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `curl -s -b '<cookie>' localhost:3100/admin/users | grep -o '<title>[^<]*'` → `<title>Usuarios · AstroBooks`.
- [ ] `/login` → `<title>Iniciar sesión · AstroBooks`; `/` → `<title>Libros · AstroBooks`.
- [ ] `/jobs/<id>` muestra el nombre del libro en el título.
- [ ] El resto de rutas tiene un título propio (revisar las 13 rutas de `npm run build`).

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: ninguna funcional.
