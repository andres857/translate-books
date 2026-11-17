# 03 · Aceptación: Pedir otra recomposición mientras se recompone pierde la petición

Ficha: [03-recomposicion-pierde-paginas.md](03-recomposicion-pierde-paginas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: con una recomposición en curso, una segunda petición se rechaza con 409 **o** (según la decisión) se recompone también; nunca se pierde en silencio.
  - Verificado: `test_second_recompose_rejected_while_recomposing` (409 con la primera en `queued` y en `running`, `options.recompose` sigue `[3]`, y tras terminar la segunda se acepta) y `test_concurrent_recompose_loses_nothing` (carrera entre lectura y escritura: 409 sin pisar la otra) en verde; ambos fallan sin la corrección (commit 30a919f).
- [x] Test nuevo: tras recomponer, `options` no conserva páginas ya hechas ni `recompose_error` de la vez anterior.
  - Verificado: `test_recompose_clears_done_pages_and_previous_error`: una recomposición que falla deja `recompose_error` y quita `recompose`; la siguiente correcta deja `options` sin ninguna de las dos claves. Este test ya pasaba antes (protege el comportamiento del worker).
- [x] La decisión tomada queda escrita en las Notas de esta ficha.
  - Verificado: sección «Notas» de la ficha, opción (a).

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 152 passed, 1 skipped, 5 deselected (antes 149 passed + 3 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Pendiente de verificación manual: el #15 sigue abierto (ruff y `alembic check` no están instalados).
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos, reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y el contenedor `api` contiene el nuevo mensaje 409.
- [ ] Regresión: en la revisión del admin, corregir un bloque y recomponer su página sigue funcionando (test `test_edit_and_recompose_only_that_page` en verde y prueba manual con un libro QA).
  - Verificado (parte automática): `test_edit_and_recompose_only_that_page` en verde.
  - Pendiente de verificación manual: corregir y recomponer con un libro QA en localhost:3100 (cuentas QA no autorizadas en esta tarea).
