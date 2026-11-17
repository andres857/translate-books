# 03 · Aceptación: Glosario y términos: el formulario se vacía aunque falle el guardado

Ficha: [03-terms-pierde-formulario-en-error.md](03-terms-pierde-formulario-en-error.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con el api detenido, al «Añadir» una entrada de glosario se muestra el error y `source`/`target` conservan lo escrito.
- [ ] Con el api detenido, al «Añadir» un término protegido se muestra el error y el campo conserva el término.
- [ ] Con el api detenido, al guardar la edición de una traducción del glosario la fila sigue en modo edición con el texto escrito.
- [ ] Con el api en marcha, las tres operaciones guardan, recargan la lista y limpian el formulario (comportamiento actual).

## Comprobaciones comunes

- [ ] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
- [ ] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
- [ ] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
- [ ] Regresión de la vista afectada: añadir, editar y borrar glosario y términos en `/admin/jobs/<id>`.
