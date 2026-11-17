# 12 · Faltan `error.tsx` y `not-found.tsx`

- **Severidad:** Medio
- **Categoría:** Estados (convenciones de Next)
- **Estado:** resuelto · commit `1030a06` · criterios verificados en [12-sin-error-not-found.aceptacion.md](12-sin-error-not-found.aceptacion.md)
- **Ubicación:** `frontend/app/` (no existen `error.tsx`, `global-error.tsx` ni `not-found.tsx`)
- **Aceptación:** [12-sin-error-not-found.aceptacion.md](12-sin-error-not-found.aceptacion.md)

## Problema

Una excepción durante el render muestra la pantalla de error por defecto de Next, sin estilo ni salida. Una ruta inexistente muestra la 404 por defecto. Un id de libro inexistente muestra un mensaje suelto dentro de una tarjeta (ver #06).

## Cómo reproducirlo

Abrir `http://localhost:3100/no-existe` (con sesión): se ve la 404 genérica de Next, sin la barra lateral ni los estilos de la app.

## Impacto

Errores poco claros y sin camino de vuelta para el usuario.

## Corrección propuesta

Crear `app/not-found.tsx` (mensaje y enlace a Libros, con los estilos de `handoff/`) y `app/error.tsx` (Client Component con `reset()` y enlace a Libros). Opcional: `app/global-error.tsx` para fallos del layout.
