# 03 · Glosario y términos: el formulario se vacía aunque falle el guardado

- **Severidad:** Medio
- **Categoría:** Bug (pérdida de datos)
- **Estado:** abierto
- **Ubicación:** `frontend/app/admin/jobs/[id]/terms.tsx:71-72`, `:78-85`, `:131`, `:198`
- **Aceptación:** [03-terms-pierde-formulario-en-error.aceptacion.md](03-terms-pierde-formulario-en-error.aceptacion.md)

## Problema

`run()` captura el error y resuelve igual:

```ts
async function run(action) { try { await action(); await load(); } catch (e) { setError(...) } }
```

Por eso lo que viene después se ejecuta también cuando la operación falla:

- `:131` `run(() => addGlossary(...)).then(() => setG({ ...g, source: "", target: "" }))`
- `:198` `run(() => addTerm(...)).then(() => setT({ ...t, term: "" }))`
- `:71-72` `await run(() => editGlossary(...)); setEditing(null);`

## Cómo reproducirlo

Como admin, en un libro › «Glosario y términos», añadir una entrada con el backend detenido (`docker compose stop api`) o con un valor que el servidor rechace: aparece el error y los campos quedan vacíos.

## Impacto

El admin pierde lo que escribió (a veces términos largos o varias entradas) y tiene que reescribirlo.

## Corrección propuesta

Que `run()` devuelva `true`/`false` (o relance el error) y limpiar o cerrar la edición solo si salió bien.
