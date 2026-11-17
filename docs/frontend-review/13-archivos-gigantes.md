# 13 · Archivos con demasiadas responsabilidades

- **Severidad:** Medio
- **Categoría:** Estructura / mantenibilidad
- **Estado:** resuelto · commits `8207e98`, `4989d9c`, `1397313` · criterios verificados en [13-archivos-gigantes.aceptacion.md](13-archivos-gigantes.aceptacion.md)
- **Ubicación:** `frontend/app/admin/playground/page.tsx` (865 líneas), `frontend/app/admin/playground/scope-view.tsx` (562), `frontend/lib/api.ts` (793)
- **Aceptación:** [13-archivos-gigantes.aceptacion.md](13-archivos-gigantes.aceptacion.md)

## Problema

- `lib/api.ts` mezcla tipos, sesión y CSRF, subida por XHR con respaldo y los endpoints de todas las áreas
  (libros, ajustes, administración, glosario, playground, usuarios).
- `admin/playground/page.tsx` concentra unos 30 estados, la carga inicial desde la URL, la estimación, el
  seguimiento de ejecuciones, la preparación de libros y el render de varias zonas.

## Cómo reproducirlo

`wc -l frontend/lib/api.ts frontend/app/admin/playground/page.tsx frontend/app/admin/playground/scope-view.tsx`.

## Impacto

Cuesta revisar y probar los cambios, y aumenta el riesgo de errores como los del #05. Varios efectos necesitan `eslint-disable` para funcionar.

## Corrección propuesta

Dividir `lib/api.ts` por área (`lib/api/http.ts` con `apiFetch`/`parse`/`ApiError`, más `jobs.ts`, `auth.ts`, `playground.ts`…), manteniendo los imports de `@/lib/api` mediante un `index.ts`. En el Playground, extraer hooks (`useRunTracking`, `usePrepareUpload`, `useEstimate`) y dejar la página como composición.

## Notas

Refactor sin cambio de comportamiento. Hacerlo después del #14 y en commits pequeños.
