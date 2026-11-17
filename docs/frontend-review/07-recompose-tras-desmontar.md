# 07 · Recomponer: el bucle de espera sigue tras salir de la vista

- **Severidad:** Bajo
- **Categoría:** Robustez
- **Estado:** abierto
- **Ubicación:** `frontend/app/admin/jobs/[id]/compare.tsx:219-243` (`recompose`)
- **Aceptación:** [07-recompose-tras-desmontar.aceptacion.md](07-recompose-tras-desmontar.aceptacion.md)

## Problema

`recompose()` espera con `while (st.status === "queued" || st.status === "running")` y un `getJob` cada 1,2 s, sin comprobar si el componente sigue montado. Al salir de la pestaña o de la página, el bucle sigue y luego llama a `setNotice`, `setVersion`, `load()` y `onChanged()`.

## Cómo reproducirlo

Como admin, pulsar «Recomponer página» y cambiar enseguida a «Resumen» o volver a «Libros»: DevTools › Network sigue mostrando `GET /api/jobs/<id>` cada 1,2 s hasta que termina.

## Impacto

Peticiones de más y actualizaciones de estado sobre un componente desmontado.

## Corrección propuesta

Una referencia `mounted` (o `AbortController`) que se marca en la limpieza de un efecto y que el bucle comprueba en cada vuelta.
