# 01 · Aceptación: Una corrección manual se pierde si se guarda mientras el libro se procesa

Ficha: [01-edicion-perdida-durante-proceso.md](01-edicion-perdida-durante-proceso.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: con el job en `queued` (recomposición pedida) o `running`, `PUT /api/admin/jobs/{id}/segments/{key}` responde **409** y el bloque no cambia en la BD.
  - Verificado: `test_edit_rejected_while_processing` (y `test_edit_during_queued_recompose_keeps_first_correction` para `queued` tras pedir recomposición) en verde; ambos fallan sin la corrección (commit 6a5443c).
- [x] Test nuevo: con el job en `done`, el mismo PUT responde 200 y `edited` queda en `true` (comportamiento actual intacto).
  - Verificado: segunda parte de `test_edit_rejected_while_processing`: 200, `edited: true` en la respuesta y en la BD.
- [x] Test nuevo de la carrera: editar → recomponer → editar otro bloque de la misma página durante `queued` es rechazado; tras `worker.process` la primera corrección sigue (`edited: true`, mismo texto).
  - Verificado: `test_edit_during_queued_recompose_keeps_first_correction`: el segundo PUT da 409 sin cambiar el bloque; tras `worker.process` el primero conserva `edited: true` y «Primera KVJX».

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 140 passed, 1 skipped, 5 deselected (línea base 138 passed + 2 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado (al cerrar el #15, sobre el código actual): `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos, reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y el contenedor `api` contiene el nuevo mensaje 409.
- [x] Regresión: en la revisión del admin, corregir un bloque y recomponer su página sigue funcionando (test `test_edit_and_recompose_only_that_page` en verde y prueba manual con un libro QA).
  - Verificado (parte automática): `test_edit_and_recompose_only_that_page` en verde.
  - Verificado (app desplegada): libro QA de 1 página y 1 bloque (#2, de qa-admin) traducido con el traductor falso dentro del contenedor `api` (`worker.process` con `runtime_settings.load` parcheado solo en ese proceso; sin tocar `data/settings.json`). En Chrome (Playwright) como qa-admin, pestaña Libro: corregir `p001_s001` y Guardar → «Corrección guardada…», insignia Editado y la corrección sigue al recargar (`edited: true`); pulsar «Recomponer página» → `queued`; en otra pestaña, Guardar otra corrección → alerta 409 «El libro se está procesando: espera a que termine para guardar correcciones.» sin cambiar el bloque, y una segunda recomposición → 409 «Ya se está recomponiendo…»; al terminar, «Página 1 recompuesta…», trabajo `done` sin `recompose_error`, el bloque conserva la corrección (`edited: true`), la vista Comparar muestra la página recompuesta con el texto corregido y el PDF de salida lo contiene. La recomposición no la ejecutó el worker desplegado (parado durante la prueba) sino `worker.process` con el traductor falso en el contenedor `api` (misma imagen): con DeepSeek activo, `translate_segments` traduce también los bloques editados antes de aplicar la corrección y la caché va por modelo, así que habría llamado a DeepSeek; log del worker sin actividad en la ventana de la prueba y ninguna fila nueva `deepseek-flash` en la caché.
