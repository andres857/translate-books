# 18 · Un fallo de red muestra «Failed to fetch» en inglés

- **Severidad:** Bajo
- **Categoría:** UX / manejo de errores
- **Estado:** resuelto · commit `00c859c` · criterios verificados en [18-error-de-red-en-ingles.aceptacion.md](18-error-de-red-en-ingles.aceptacion.md)
- **Ubicación:** `frontend/lib/api.ts` (`apiFetch`/`parse`): todas las vistas que muestran `(e as Error).message`
- **Aceptación:** [18-error-de-red-en-ingles.aceptacion.md](18-error-de-red-en-ingles.aceptacion.md)
- **Origen:** visto al verificar el #03 y el #06 con el api inalcanzable

## Problema

Si el navegador no llega al servidor, `fetch` rechaza con `TypeError: Failed to fetch` y las vistas muestran ese
texto tal cual. El resto de mensajes de la app están en español y explican qué hacer.

## Cómo reproducirlo

Con el api inalcanzable (o una petición abortada en DevTools), añadir una entrada en «Glosario y términos» o
abrir `/jobs/<id>`: el aviso dice «Failed to fetch».

## Impacto

Mensaje técnico en otro idioma justo cuando el usuario necesita saber qué pasa.

## Corrección propuesta

En `apiFetch`, capturar el rechazo de `fetch` (no las respuestas HTTP) y lanzar un `ApiError` con estado 0 y un
mensaje en español: «No hay conexión con el servidor. Comprueba que el servicio esté en marcha e inténtalo de
nuevo.». `xhrSend` ya tiene su propio mensaje (`LOST`).
