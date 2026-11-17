# 15 · Aceptación: Todas las pestañas del navegador tienen el mismo título

Ficha: [15-titulos-por-pagina.md](15-titulos-por-pagina.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `curl -s -b '<cookie>' localhost:3100/admin/users | grep -o '<title>[^<]*'` → `<title>Usuarios · AstroBooks`.
  - Verificado: HTML servido a una petición con la cookie de qa-admin (equivale al curl con cookie): /admin/users → `<title>Usuarios · AstroBooks`.
- [x] `/login` → `<title>Iniciar sesión · AstroBooks`; `/` → `<title>Libros · AstroBooks`.
  - Verificado: /login sin sesión → `Iniciar sesión · AstroBooks`; / → `Libros · AstroBooks`.
- [x] `/jobs/<id>` muestra el nombre del libro en el título.
  - Verificado: Chrome en /jobs/7 → «Página de qa uno · AstroBooks»; /admin/jobs/7 → «Página de qa uno · Revisión · AstroBooks».
- [x] El resto de rutas tiene un título propio (revisar las 13 rutas de `npm run build`).
  - Verificado: títulos servidos: Configuración, Prompts, Playground, Historial del Playground (corregido en f85e125: le faltaba «· AstroBooks»), Revisión del libro, Libro, Cambiar contraseña y Página no encontrada, todos «… · AstroBooks». /admin y /settings solo redirigen.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: ninguna funcional.
  - Verificado: sin cambios funcionales: solo títulos.
