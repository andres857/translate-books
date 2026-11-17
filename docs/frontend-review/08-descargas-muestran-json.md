# 08 · Las descargas que fallan muestran JSON en crudo

- **Severidad:** Bajo
- **Categoría:** UX / manejo de errores
- **Estado:** resuelto · commits `b261e8f`, `ac640da` · criterios verificados en [08-descargas-muestran-json.aceptacion.md](08-descargas-muestran-json.aceptacion.md)
- **Ubicación:** `frontend/app/jobs/[id]/page.tsx:157-161` y `frontend/app/admin/jobs/[id]/page.tsx:115-125`
- **Aceptación:** [08-descargas-muestran-json.aceptacion.md](08-descargas-muestran-json.aceptacion.md)

## Problema

Las descargas son enlaces `<a href="/api/jobs/<id>/download...">`. Si el servidor responde con error (409: aún no está listo o se está recomponiendo; 401: sesión caducada; 500 al generar el EPUB o el AZW3), el navegador navega a la respuesta y muestra el JSON `{"statusCode":...}`.

## Cómo reproducirlo

Como admin, recomponer una página y pulsar «Descargar PDF» mientras dura, o esperar a que caduque la sesión (30 min de inactividad) y pulsar una descarga.

## Impacto

El usuario sale de la app hacia una página de error técnica y tiene que volver atrás.

## Corrección propuesta

Descargar con `apiFetch` + `blob` + `URL.createObjectURL` y mostrar el mensaje en un `alert` de la página. Ante un 401, `parse()` ya dispara la vuelta al login. Alternativa mínima: deshabilitar los botones mientras `recomposing`.

## Notas

Decidir si el cambio compensa: los archivos pueden ser grandes (un PDF de 200 MB en memoria con `blob`). Alternativa sin `blob`: comprobar con `HEAD` o con el estado antes de navegar.
