# 03 · Aceptación: Glosario y términos: el formulario se vacía aunque falle el guardado

Ficha: [03-terms-pierde-formulario-en-error.md](03-terms-pierde-formulario-en-error.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con el api detenido, al «Añadir» una entrada de glosario se muestra el error y `source`/`target` conservan lo escrito.
  - Verificado: Chrome como qa-admin en /admin/jobs/4 › Glosario, con las escrituras a /api/glossary abortadas solo en ese navegador (equivale a api caído): aparece el error y los campos conservan «qa-zodiac» / «qa-zodiaco».
- [x] Con el api detenido, al «Añadir» un término protegido se muestra el error y el campo conserva el término.
  - Verificado: mismo escenario con /api/protected-terms: el campo conserva «QA-Brand».
- [x] Con el api detenido, al guardar la edición de una traducción del glosario la fila sigue en modo edición con el texto escrito.
  - Verificado: editando la traducción con la escritura abortada: la fila sigue en edición con «qa-zodiaco-editado».
- [x] Con el api en marcha, las tres operaciones guardan, recargan la lista y limpian el formulario (comportamiento actual).
  - Verificado: sin fallo: el alta de glosario y la de término guardan y vacían los campos, la edición se guarda y se cierra («qa-zodiaco-editado» en la tabla).

## Comprobaciones comunes

- [x] `cd frontend && npx tsc --noEmit` termina sin errores (salida vacía, código 0).
  - Verificado: `npx tsc --noEmit` → sin salida, código 0.
- [x] `cd frontend && node ../handoff/check.mjs app lib` imprime `Problemas: 0`.
  - Verificado: `node ../handoff/check.mjs app lib` → `Problemas: 0`.
- [x] `cd frontend && npm run build` termina con la tabla de rutas y sin errores.
  - Verificado: `npm run build` → tabla de rutas sin errores.
- [x] Regresión de la vista afectada: añadir, editar y borrar glosario y términos en `/admin/jobs/<id>`.
  - Verificado: Chrome: añadir, editar y quitar una entrada de glosario y un término protegido en /admin/jobs/4; al final no queda ninguna fila «qa-».
