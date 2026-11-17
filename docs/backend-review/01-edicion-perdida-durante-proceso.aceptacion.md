# 01 · Aceptación: Una corrección manual se pierde si se guarda mientras el libro se procesa

Ficha: [01-edicion-perdida-durante-proceso.md](01-edicion-perdida-durante-proceso.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: con el job en `queued` (recomposición pedida) o `running`, `PUT /api/admin/jobs/{id}/segments/{key}` responde **409** y el bloque no cambia en la BD.
- [ ] Test nuevo: con el job en `done`, el mismo PUT responde 200 y `edited` queda en `true` (comportamiento actual intacto).
- [ ] Test nuevo de la carrera: editar → recomponer → editar otro bloque de la misma página durante `queued` es rechazado; tras `worker.process` la primera corrección sigue (`edited: true`, mismo texto).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: en la revisión del admin, corregir un bloque y recomponer su página sigue funcionando (test `test_edit_and_recompose_only_that_page` en verde y prueba manual con un libro QA).
