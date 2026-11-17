# 10 · Aceptación: Nada en la BD impide duplicados en bloques, glosario y términos

Ficha: [10-sin-unique-duplicados.md](10-sin-unique-duplicados.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: añadir dos veces la misma entrada de glosario (mismo libro o global, distinto uso de mayúsculas) → la segunda responde **409** y hay una sola fila.
- [ ] Test nuevo: lo mismo con términos protegidos.
- [ ] Test nuevo: insertar dos `Segment` con el mismo `seg_key` en la misma página lanza `IntegrityError`.
- [ ] La respuesta 409 no contiene texto de SQLite (`UNIQUE constraint`, nombres de tabla).
- [ ] Antes de migrar, las consultas de duplicados sobre una copia de la BD real devuelven 0 filas (anotado en «Verificado»).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: la pestaña Glosario y términos del admin permite añadir, editar y borrar entradas como antes.
