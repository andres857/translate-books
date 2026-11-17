# 08 · Aceptación: Las descargas que fallan muestran JSON en crudo

Ficha: [08-descargas-muestran-json.md](08-descargas-muestran-json.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con una recomposición en curso, pulsar «Descargar PDF» no abandona la app: se ve un aviso «El libro traducido todavía no está listo» (o el botón está deshabilitado).
  - Verificado: Chrome en /jobs/7 ya terminado; se lanza una recomposición por la API y se pulsa «Descargar PDF»: la URL sigue en /jobs/7 y a los 0,5 s y a los 2,5 s se ve «El libro traducido todavía no está listo: se está procesando o recomponiendo…»; al terminar, el aviso desaparece y vuelve el botón. (La primera versión lo perdía con el sondeo: se corrigió en ac640da.)
- [x] Con la sesión caducada, pulsar una descarga lleva a `/login?next=...` en lugar de mostrar JSON.
  - Verificado: sesión revocada con logout desde otra pestaña del mismo navegador; «Descargar PDF» → `/login?next=%2Fjobs%2F7`, sin JSON en pantalla.
- [x] Con todo listo, PDF, EPUB, AZW3 y el reporte se descargan con su nombre de archivo correcto.
  - Verificado: /jobs/7: «Página de qa uno (ES).pdf», «… (ES).epub», «… (ES).azw3» y «reporte-traduccion.json», sin salir de /jobs/7; /admin/jobs/7: los mismos cuatro desde el botón dividido y su menú.
- [ ] Descargar un PDF grande (≥ 100 MB) no congela la pestaña ni dispara la memoria (Administrador de tareas del navegador).
  - Pendiente de verificación manual: no hay ningún PDF ≥ 100 MB en esta instalación (el mayor, el libro 1, pesa 65 MB). Con ese archivo: descarga en 1 s, memoria JS de la pestaña de 16,7 a 17,4 MB y la pestaña responde. La descarga es un enlace normal (sin blob), así que el tamaño no pasa por la memoria de la pestaña.

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: descargar PDF, EPUB, AZW3 y el reporte desde ambas vistas.
  - Verificado: descargas de PDF, EPUB, AZW3 y reporte desde /jobs/7 y /admin/jobs/7 (arriba).
