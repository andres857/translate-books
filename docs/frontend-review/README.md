# Revisión del frontend (noviembre 2026)

Revisión de `frontend/` (Next.js 16.4.5, App Router, React 19) sin cambios de código. Cada problema tiene su
ficha (`NN-slug.md`: qué pasa, cómo reproducirlo, impacto y corrección propuesta) y su archivo de aceptación
(`NN-slug.aceptacion.md`: casillas con resultados verificables). Las casillas empiezan vacías (`- [ ]`) y se
marcan (`- [x]`) al comprobarlas tras el arreglo.

## Línea base

- `npx tsc --noEmit`: sin errores.
- `node ../handoff/check.mjs app lib`: `Problemas: 0`.
- `npm run build`: correcto, 13 rutas dinámicas + proxy.
- ESLint: no instalado. Tests: no hay (ver #14).

## Estado final (17 de noviembre de 2026)

- Resueltos con todos sus criterios verificados: los 15 de la revisión y tres encontrados durante el trabajo
  (#17 límite de login compartido, #18 mensaje de red en inglés, #19 cambio obligatorio sin llegar a Libros).
- Abierto: #16 (setState dentro de efectos, 20 casos). ESLint lo deja en aviso hasta resolverlo.
- `npm run lint`: 19 problems (0 errors, 19 warnings) (todos del #16). `npm run test`: Tests 20 passed (20). `npm run test:e2e`: 1 passed.
  `npm run build`: correcto. Backend `pytest -q -m "not slow and not s3"`: 138 passed, 1 skipped, 5 deselected, 1 warning in 41.23s.
- Verificación en navegador con Chrome (Playwright) y las cuentas `qa-admin@astrobooks.local` y
  `qa-user@astrobooks.local`, desactivadas al terminar.

## Problemas

| # | Severidad | Problema | Aceptación | Estado |
|---|---|---|---|---|
| 01 | Crítico | [Redirección abierta en el `?next=` del login](01-open-redirect-login.md) | [criterios](01-open-redirect-login.aceptacion.md) | resuelto (24f5f04) |
| 02 | Alto | [Enlaces a Configuración visibles para usuarios sin rol admin](02-enlaces-configuracion-usuario.md) | [criterios](02-enlaces-configuracion-usuario.aceptacion.md) | resuelto (70e8ac8) |
| 03 | Medio | [Glosario y términos: el formulario se vacía aunque falle el guardado](03-terms-pierde-formulario-en-error.md) | [criterios](03-terms-pierde-formulario-en-error.aceptacion.md) | resuelto (505f5fa) |
| 04 | Medio | [Vista Libro: cambiar de página descarta las correcciones sin guardar](04-compare-descarta-borradores.md) | [criterios](04-compare-descarta-borradores.aceptacion.md) | resuelto (97d7289) |
| 05 | Medio | [Respuestas antiguas sobrescriben la vista actual (carreras)](05-carreras-en-cargas.md) | [criterios](05-carreras-en-cargas.aceptacion.md) | resuelto (b443972) |
| 06 | Bajo | [Progreso del libro: consulta cada 4 s para siempre ante un 404](06-polling-infinito-404.md) | [criterios](06-polling-infinito-404.aceptacion.md) | resuelto (b53c76c) |
| 07 | Bajo | [Recomponer: el bucle de espera sigue tras salir de la vista](07-recompose-tras-desmontar.md) | [criterios](07-recompose-tras-desmontar.aceptacion.md) | resuelto (845e177) |
| 08 | Bajo | [Las descargas que fallan muestran JSON en crudo](08-descargas-muestran-json.md) | [criterios](08-descargas-muestran-json.aceptacion.md) | resuelto (b261e8f, ac640da) |
| 09 | Bajo | [Trabajo en `paused`: sin botón «Reanudar» y sondeo sin fin](09-estado-paused-sin-reanudar.md) | [criterios](09-estado-paused-sin-reanudar.aceptacion.md) | resuelto (a2b52ff) |
| 10 | Bajo | [Efecto secundario dentro de la función de `setDisc`](10-efecto-dentro-de-setstate.md) | [criterios](10-efecto-dentro-de-setstate.aceptacion.md) | resuelto (e1073f3) |
| 11 | Medio | [Todas las páginas son de cliente: el HTML del servidor solo trae «Cargando…»](11-todo-en-cliente.md) | [criterios](11-todo-en-cliente.aceptacion.md) | resuelto (a751dfb, 2591661) |
| 12 | Medio | [Faltan `error.tsx` y `not-found.tsx`](12-sin-error-not-found.md) | [criterios](12-sin-error-not-found.aceptacion.md) | resuelto (1030a06) |
| 13 | Medio | [Archivos con demasiadas responsabilidades](13-archivos-gigantes.md) | [criterios](13-archivos-gigantes.aceptacion.md) | resuelto (8207e98, 4989d9c, 1397313) |
| 14 | Medio | [Sin ESLint ni tests: hay `eslint-disable` que no comprueba nadie](14-sin-eslint-ni-tests.md) | [criterios](14-sin-eslint-ni-tests.aceptacion.md) | resuelto (5528cb1) |
| 15 | Bajo | [Todas las pestañas del navegador tienen el mismo título](15-titulos-por-pagina.md) | [criterios](15-titulos-por-pagina.aceptacion.md) | resuelto (4546c62, f85e125) |
| 16 | Medio | [setState síncrono dentro de efectos (20 casos)](16-setstate-en-efectos.md) | [criterios](16-setstate-en-efectos.aceptacion.md) | abierto |
| 17 | Alto | [El límite de intentos por IP es compartido por todos los usuarios](17-limite-login-ip-compartida.md) | [criterios](17-limite-login-ip-compartida.aceptacion.md) | resuelto (48f7dd2) |
| 18 | Bajo | [Un fallo de red muestra «Failed to fetch» en inglés](18-error-de-red-en-ingles.md) | [criterios](18-error-de-red-en-ingles.aceptacion.md) | resuelto (00c859c) |
| 19 | Bajo | [Tras el cambio obligatorio de contraseña no se llega a Libros](19-cambio-obligatorio-no-lleva-a-libros.md) | [criterios](19-cambio-obligatorio-no-lleva-a-libros.aceptacion.md) | resuelto (b5fcb48) |

## Orden recomendado

1. #01 y #02: arreglos pequeños y localizados (seguridad y permisos en la UI).
2. #03, #04 y #05: pérdida de datos y carreras en la revisión del admin.
3. #06, #07, #09 y #10: robustez menor. #08 requiere decidir el enfoque (ver Notas de su ficha).
4. #14: ESLint y smoke tests, antes de tocar la estructura.
5. #12, luego #11, #13 y #15: cambios estructurales graduales, un commit por paso.
6. #16 (encontrado por ESLint en el #14): por archivos, junto con #13 cuando toque el mismo archivo.

## Comportamientos de regresión

Se repasan a mano tras cada arreglo (hasta que exista el smoke test del #14):

- Login, cambio obligatorio de contraseña, logout y redirección con `?next=`.
- `user`: ver sus libros, subir un PDF, ver el progreso, cancelar, reanudar y descargar.
- `admin`: borrar un libro, la vista de revisión (Libro, Glosario y términos, Resumen), corregir y recomponer
  una página, Configuración, Usuarios y Playground.
