# 17 · Aceptación: El CHECK del rol existe en la BD pero no en el modelo

Ficha: [17-check-rol-solo-en-migracion.md](17-check-rol-solo-en-migracion.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: `Base.metadata.tables['users']` contiene un `CheckConstraint` llamado `ck_users_role`.
- [ ] Test nuevo: insertar un usuario con `role='root'` lanza `IntegrityError`.
- [ ] `alembic check` (test del #15) sigue sin detectar operaciones pendientes.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: gestión de usuarios del admin sigue funcionando.
