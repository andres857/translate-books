# 03 · Aceptación: Pedir otra recomposición mientras se recompone pierde la petición

Ficha: [03-recomposicion-pierde-paginas.md](03-recomposicion-pierde-paginas.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: con una recomposición en curso, una segunda petición se rechaza con 409 **o** (según la decisión) se recompone también; nunca se pierde en silencio.
- [ ] Test nuevo: tras recomponer, `options` no conserva páginas ya hechas ni `recompose_error` de la vez anterior.
- [ ] La decisión tomada queda escrita en las Notas de esta ficha.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: en la revisión del admin, corregir un bloque y recomponer su página sigue funcionando (test `test_edit_and_recompose_only_that_page` en verde y prueba manual con un libro QA).
