# 01 · Una corrección manual se pierde si se guarda mientras el libro se procesa

- **Severidad:** Alto
- **Categoría:** Integridad de datos
- **Estado:** resuelto · commit(s) `6a5443c`
- **Ubicación:** `backend/app/api/routes_admin.py:116-135` (`edit_segment`), `backend/app/worker.py:68-91` (`save_results`) y `:178-205` (`process_recompose`)
- **Aceptación:** [01-edicion-perdida-durante-proceso.aceptacion.md](01-edicion-perdida-durante-proceso.aceptacion.md)

## Problema

`PUT /api/admin/jobs/{id}/segments/{key}` guarda la traducción corregida sin mirar el estado del trabajo.
Pero el worker, al recomponer (o al procesar el libro entero), **borra las páginas y las vuelve a crear** desde
lo que leyó al empezar:

```python
for row in old.all():  # por el ORM, para que se borren también sus segmentos
    s.delete(row)
```

`process_recompose` lee los bloques editados de la página **antes** de recomponerla; lo que se edite después en
esa página desaparece cuando `save_results(..., only={n})` reescribe la página.

## Cómo reproducirlo

1. Con un libro terminado, pedir «Recomponer» la página N (`POST …/pages/N/recompose`).
2. Mientras el job está `queued`/`running`, guardar otra corrección en un bloque de la página N.
3. Al terminar, `GET …/pages/N/segments`: el bloque ya no tiene la corrección ni `edited: true`.

Con un test: encolar la recomposición, editar un bloque de esa página y luego ejecutar `worker.process`.

## Impacto

El admin pierde trabajo manual sin aviso; la respuesta del PUT fue 200, así que cree que está guardado.

## Corrección propuesta

Rechazar la edición con 409 («El libro se está procesando: espera a que termine») cuando el trabajo esté en `queued` o `running`. Opcional: que el frontend lo muestre (ya muestra los 409 como aviso).

## Notas

El botón de guardar del frontend (`compare.tsx`) solo depende del estado local `busy`, no del estado del job. En un procesamiento completo (reanudar un libro fallido) pasa lo mismo con todas las páginas.
