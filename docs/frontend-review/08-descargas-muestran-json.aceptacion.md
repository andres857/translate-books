# 08 · Aceptación: Las descargas que fallan muestran JSON en crudo

Ficha: [08-descargas-muestran-json.md](08-descargas-muestran-json.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con una recomposición en curso, pulsar «Descargar PDF» no abandona la app: se ve un aviso «El libro traducido todavía no está listo» (o el botón está deshabilitado).
- [ ] Con la sesión caducada, pulsar una descarga lleva a `/login?next=...` en lugar de mostrar JSON.
- [ ] Con todo listo, PDF, EPUB, AZW3 y el reporte se descargan con su nombre de archivo correcto.
- [ ] Descargar un PDF grande (≥ 100 MB) no congela la pestaña ni dispara la memoria (Administrador de tareas del navegador).

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: descargar PDF, EPUB, AZW3 y el reporte desde ambas vistas.
