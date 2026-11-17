# 15 · Todas las pestañas del navegador tienen el mismo título

- **Severidad:** Bajo
- **Categoría:** SEO / UX
- **Estado:** resuelto · commits `4546c62`, `f85e125` · criterios verificados en [15-titulos-por-pagina.aceptacion.md](15-titulos-por-pagina.aceptacion.md)
- **Ubicación:** `frontend/app/layout.tsx` (única `metadata`: «AstroBooks · Traductor de libros»)
- **Aceptación:** [15-titulos-por-pagina.aceptacion.md](15-titulos-por-pagina.aceptacion.md)

## Problema

Ninguna página define `metadata` ni `generateMetadata`. Como todas son `"use client"` (ver #11), no pueden exportarla.

## Cómo reproducirlo

Abrir Libros, un libro y Usuarios en tres pestañas: las tres se llaman «AstroBooks · Traductor de libros».

## Impacto

Cuesta distinguir las pestañas y el historial del navegador.

## Corrección propuesta

Usar `title.template` en el layout (`"%s · AstroBooks"`) y `metadata` por página; donde la página sea cliente, añadir un `layout.tsx` de servidor por segmento que la exporte. Los títulos con datos (el nombre del libro) necesitan `generateMetadata` en un segmento de servidor.

## Notas

Depende en parte del #11 para los títulos con datos.
