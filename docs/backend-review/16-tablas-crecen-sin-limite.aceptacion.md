# 16 · Aceptación: Sesiones, intentos de login, eventos y caché crecen sin límite

Ficha: [16-tablas-crecen-sin-limite.md](16-tablas-crecen-sin-limite.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: `purge` borra sesiones revocadas/caducadas más antiguas que el umbral y conserva las vigentes.
- [ ] Test nuevo: borra eventos más antiguos que la retención y conserva los recientes.
- [ ] `python -m app.cli purge --dry-run` sobre una copia de la BD real informa cuántas filas borraría por tabla sin borrar nada.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: login, sesión activa y bitácora de seguridad siguen funcionando.
