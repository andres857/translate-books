# 20 · Aceptación: Al borrar un libro, glosario, términos e intentos se borran fila a fila

Ficha: [20-borrado-glosario-fila-a-fila.md](20-borrado-glosario-fila-a-fila.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo con `count_queries`: `DELETE /api/jobs/{id}` hace el mismo número de queries con 1 y con 50 entradas de glosario y términos del documento, y con 0 y 5 intentos del Playground.
- [ ] Tras el borrado no quedan entradas de glosario ni términos del documento, ni intentos del trabajo, y los PDF de los intentos se borran del disco.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: borrar un libro QA desde la app (admin) sigue funcionando y deja la BD sin filas suyas.
