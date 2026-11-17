# 06 · Progreso del libro: consulta cada 4 s para siempre ante un 404

- **Severidad:** Bajo
- **Categoría:** Robustez
- **Estado:** resuelto · commit `b53c76c` · criterios verificados en [06-polling-infinito-404.aceptacion.md](06-polling-infinito-404.aceptacion.md)
- **Ubicación:** `frontend/app/jobs/[id]/page.tsx:63-67`
- **Aceptación:** [06-polling-infinito-404.aceptacion.md](06-polling-infinito-404.aceptacion.md)

## Problema

En el `catch` del sondeo, cualquier error reprograma `tick` a los 4 s, también un 404 (el trabajo no existe o es de otro usuario) o un 403.

## Cómo reproducirlo

Abrir `http://localhost:3100/jobs/999999`: DevTools › Network muestra una petición a `/api/jobs/999999` cada 4 s mientras la pestaña siga abierta.

## Impacto

Tráfico y carga inútiles. El mensaje de error se queda sin salida (no hay enlace de vuelta salvo «Libros»).

## Corrección propuesta

Dejar de sondear ante `ApiError` con `status` 404/403 y mostrar un estado «no encontrado» con enlace a Libros. Reintentar solo ante errores de red o 5xx.

## Notas

`ApiError` (`frontend/lib/api.ts`) ya expone `status` y `code`.
