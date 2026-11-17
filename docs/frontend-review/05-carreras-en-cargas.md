# 05 · Respuestas antiguas sobrescriben la vista actual (carreras)

- **Severidad:** Medio
- **Categoría:** Datos (condición de carrera)
- **Estado:** resuelto · commit `b443972` · criterios verificados en [05-carreras-en-cargas.aceptacion.md](05-carreras-en-cargas.aceptacion.md)
- **Ubicación:** `frontend/app/admin/jobs/[id]/compare.tsx:137-145` (`load`) y `frontend/app/admin/playground/page.tsx:146-169` (`listChapters`)
- **Aceptación:** [05-carreras-en-cargas.aceptacion.md](05-carreras-en-cargas.aceptacion.md)

## Problema

- `compare.tsx`: `load` hace `setInfo(await getSegments(job.id, page))` sin comprobar que `page` siga
  siendo la actual. Si se pasan varias páginas rápido, la respuesta más lenta gana.
- `playground/page.tsx`: el efecto de `bookId` hace `listChapters(bookId).then(chs => setChapters(chs) ...)`
  sin guardia `alive`, a diferencia de los otros efectos del mismo archivo (estimación y página).

## Cómo reproducirlo

Con la red ralentizada (DevTools › Network › Slow 3G): en «Libro», pulsar → tres veces seguidas y ver que los bloques mostrados no corresponden a la página visible. En el Playground, cambiar de libro dos veces seguidas y ver los capítulos del libro anterior.

## Impacto

Se muestran (y se pueden editar) bloques de otra página, o se elige alcance con capítulos de otro libro.

## Corrección propuesta

Guardia `alive` en el efecto (o `AbortController` si `apiFetch` acepta `signal`) e ignorar respuestas cuyo `page`/`bookId` ya no es el actual.

## Notas

El patrón correcto ya existe en `playground/page.tsx` (efecto de `pageKey`, `let alive = true`).
