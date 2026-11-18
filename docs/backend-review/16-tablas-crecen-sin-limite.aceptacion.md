# 16 · Aceptación: Sesiones, intentos de login, eventos y caché crecen sin límite

Ficha: [16-tablas-crecen-sin-limite.md](16-tablas-crecen-sin-limite.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: `purge` borra sesiones revocadas/caducadas más antiguas que el umbral y conserva las vigentes.
  - Verificado: `test_purge_sessions_older_than_threshold` (tests/test_auth.py): borra las revocadas y caducadas hace 31 días, conserva las de hace 29 días y la vigente (que sigue respondiendo 200 en `/api/auth/me`); `--dry-run` no borra. `test_purge_retention_from_settings`: el umbral sale de `AUTH_SESSIONS_RETENTION_DAYS`.
- [x] Test nuevo: borra eventos más antiguos que la retención y conserva los recientes.
  - Verificado: `test_purge_events_and_expired_rate_limits`: borra el evento de hace 181 días y conserva el de 179; borra la ventana de rate limit vencida (16 min) y conserva la vigente (14 min); no informa de `translation_cache`.
- [x] `python -m app.cli purge --dry-run` sobre una copia de la BD real informa cuántas filas borraría por tabla sin borrar nada.
  - Verificado: copia por `backup()` de sqlite3 desde `file:data/app.db?mode=ro`; con `DATABASE_URL` a la copia: `auth_sessions: 0`, `auth_rate_limits: 3`, `auth_security_events: 0` «se borrarían» (todos los datos son de hoy; con retenciones a 0 días: 113 / 3 / 183, de 114 sesiones y 183 eventos). SHA-256 de la copia idéntico antes y después (`863e2e30…`); conteos sin cambios (114, 3, 183, caché 2141). `test_cli_purge_dry_run_deletes_nothing` lo cubre en los tests.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 187 passed, 1 skipped, 5 deselected (183 + 4 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración (solo borra filas de tablas existentes; la BD sigue en `f3b5d7e9a1c4`).
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos; `api` y `worker` reconstruidos; health `{"ok":true}`, `/login` 200; `docker compose exec -T api python -m app.cli purge --help` muestra `--dry-run`.
- [x] Regresión: login, sesión activa y bitácora de seguridad siguen funcionando.
  - Verificado (parte automática): `tests/test_auth*.py` en verde (login, logout, rate limit, sesiones y bitácora); la purga no cambia ningún endpoint.
  - Verificado (app desplegada): Chrome como qa-user: login con contraseña mala → 401; login por la UI → / y `/api/auth/me` 200 (qa-user, user); al recargar sigue dentro (sesión activa); «Cerrar sesión» → /login y `/api/auth/me` 401; tras desactivarla desde Usuarios, su login → 401. La bitácora (`auth_security_events`, leída en solo lectura; la app no tiene vista para ella) registra en orden `login_failed`, `login`, `logout`, `login` (qa-admin), `reauth`, `user_updated` (actor qa-admin) y `login_failed`.
