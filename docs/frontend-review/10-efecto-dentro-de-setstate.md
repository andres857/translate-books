# 10 · Efecto secundario dentro de la función de `setDisc`

- **Severidad:** Bajo
- **Categoría:** Pureza (React)
- **Estado:** abierto
- **Ubicación:** `frontend/app/admin/jobs/[id]/terms.tsx:44-47`
- **Aceptación:** [10-efecto-dentro-de-setstate.aceptacion.md](10-efecto-dentro-de-setstate.aceptacion.md)

## Problema

Dentro de la función que actualiza el estado se lanza una recarga:

```ts
setDisc((prev) => { if (prev?.status === "running" && d.status !== "running") load(); return d; });
```

Las funciones de actualización deben ser puras: React puede llamarlas dos veces (StrictMode en desarrollo).

## Cómo reproducirlo

En `next dev` (StrictMode), lanzar «Descubrir glosario» y esperar a que termine: DevTools › Network muestra `GET /api/glossary` y `GET /api/protected-terms` duplicados al terminar.

## Impacto

Peticiones duplicadas y un patrón frágil ante cambios de React.

## Corrección propuesta

Comparar el estado anterior fuera de la función de actualización (una ref con el estado previo, o un efecto que reaccione a `disc.status` pasando de `running` a otro) y llamar a `load()` ahí.
