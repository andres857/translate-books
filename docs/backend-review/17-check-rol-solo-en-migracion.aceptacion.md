# 17 · Aceptación: El CHECK del rol existe en la BD pero no en el modelo

Ficha: [17-check-rol-solo-en-migracion.md](17-check-rol-solo-en-migracion.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: `Base.metadata.tables['users']` contiene un `CheckConstraint` llamado `ck_users_role`.
  - Verificado: `test_user_model_declares_role_check` (tests/test_tooling.py) en verde; falla si se quita el `CheckConstraint` del modelo. En el contenedor desplegado: `['pk_users', 'uq_users_email', 'ck_users_role']`.
- [x] Test nuevo: insertar un usuario con `role='root'` lanza `IntegrityError`.
  - Verificado: `test_create_all_rejects_unknown_role` (BD en memoria con `Base.metadata.create_all`, sin Alembic): `role='user'` entra y `role='root'` lanza `IntegrityError` con «ck_users_role»; falla sin el CHECK en el modelo.
- [x] `alembic check` (test del #15) sigue sin detectar operaciones pendientes.
  - Verificado: `test_alembic_check` en verde con el CHECK y la `naming_convention` (los nombres de la convención coinciden con los existentes; ningún renombrado).

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 173 passed, 1 skipped, 5 deselected (171 + 2 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración (el CHECK ya existe en la BD; tras el deploy la versión sigue en `f3b5d7e9a1c4`).
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos; `api` y `worker` reconstruidos; health `{"ok":true}`, `/login` 200, versión de la BD `f3b5d7e9a1c4`.
- [x] Regresión: gestión de usuarios del admin sigue funcionando.
  - Verificado (parte automática): `test_patch_rejects_email_unknown_and_bad_role`, `test_role_change_deactivation_and_reset_revoke_sessions` y `test_user_cannot_manage_accounts` (tests/test_auth.py) en verde.
  - Verificado (app desplegada): Chrome como qa-admin en /admin/users: la lista muestra las 4 cuentas con rol, estado y alta; cambiar el rol de qa-user a Administrador (pide «Confirma tu contraseña») → «qa-user@astrobooks.local ahora es administrador. Sus sesiones se cerraron.» y de vuelta a Usuario → «… ahora es usuario…»; desactivación de qa-user y qa-admin al terminar (ver Estado final del README). Sin alta de cuentas nuevas para no dejar cuentas QA extra (cubierta por los tests).
