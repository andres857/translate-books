# 16 · Sesiones, intentos de login, eventos y caché crecen sin límite

- **Severidad:** Bajo
- **Categoría:** Mantenimiento
- **Estado:** abierto
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
