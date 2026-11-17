# 16 · Sesiones, intentos de login, eventos y caché crecen sin límite

- **Severidad:** Bajo
- **Categoría:** Mantenimiento
- **Estado:** resuelto · commit(s) `b90c42b`
- **Ubicación:** `backend/app/auth/sessions.py`, `backend/app/auth/rate_limit.py`, `backend/app/auth/events.py`, `backend/app/db/cache.py`
- **Aceptación:** [16-tablas-crecen-sin-limite.aceptacion.md](16-tablas-crecen-sin-limite.aceptacion.md)

## Problema

No hay ningún proceso que borre sesiones revocadas o caducadas, ventanas de rate limit antiguas, eventos de
seguridad viejos ni entradas de caché de modelos que ya no se usan. Hoy: 114 sesiones (113 revocadas, 12
caducadas), 183 eventos, 2141 entradas de caché.

## Cómo reproducirlo

`SELECT count(*) FROM auth_sessions WHERE revoked_at IS NOT NULL OR expires_at < datetime('now')` sobre una copia de la BD.

## Impacto

La BD crece sin control y los datos personales mínimos (IP, user agent) se guardan indefinidamente.

## Corrección propuesta

Comando `python -m app.cli purge` (y opcionalmente una pasada diaria en el worker) que borre sesiones revocadas o caducadas hace más de N días, ventanas de rate limit vencidas y eventos más antiguos que la retención configurable (`AUTH_EVENTS_RETENTION_DAYS`, p. ej. 180). La caché, solo si el usuario lo pide.

## Notas

Preguntar la retención de la bitácora antes de implementarlo.

- Decisión del usuario: `python -m app.cli purge [--dry-run]` (`backend/app/auth/purge.py`). Retenciones por
  entorno: `AUTH_SESSIONS_RETENTION_DAYS=30` (sesiones con `revoked_at` o `expires_at` de hace más de 30 días)
  y `AUTH_EVENTS_RETENTION_DAYS=180` (`auth_security_events.created_at`). Ventanas de rate limit: se borran las
  que ya vencieron (`window_start + LOGIN_WINDOW_MINUTES <= ahora`), que el siguiente intento reiniciaría a cero
  igualmente. La caché de traducciones no se purga.
- Una sesión caducada por inactividad siempre tiene `expires_at` como mucho 8 h después (`SESSION_MAX_HOURS`),
  así que el criterio por `expires_at` la cubre sin mirar `last_seen_at`.
- Pasada automática en el worker: **no** se añade (opción recomendada, la más simple y segura). El worker sigue
  dedicado a los trabajos, la purga solo borra cuando alguien la ejecuta y puede revisarse antes con
  `--dry-run`; el volumen es pequeño (cientos de filas). Si hace falta, un cron diario en el host con
  `docker compose exec -T api python -m app.cli purge` (documentado en el README).
- `purge` no llama a `migrate()` (a diferencia de otros comandos de la CLI) para que `--dry-run` no escriba nada.
