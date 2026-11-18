# 06 · Aceptación: Sin copias de seguridad de SQLite ni purga programada

Ficha: [06-datos-copias-purga.md](06-datos-copias-purga.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Tras forzar una ejecución del servicio de copia, existe `data/backups/app-<fecha>.db` y `PRAGMA integrity_check` → `ok` con las mismas filas por tabla que `data/app.db`.
  - Verificado: `docker compose run --rm backup python -m app.cli backup once` → `data/backups/app-2026-11-18.db` (25,3 MB, dueño 1000:1000), `integrity_check` `ok` y las 16 tablas con las mismas filas que `data/app.db` (pages 192, segments 3345).
- [x] La retención funciona: con más copias de las configuradas, solo quedan las N más recientes (test o prueba con fechas simuladas).
  - Verificado: `tests/test_backup.py::test_prune_keeps_newest` (10 copias → quedan las 7 más recientes; `app.db.bak-*` intactas) y, en un contenedor de prueba con `BACKUP_KEEP=2` sobre una copia en el scratchpad, la ejecución de las 05:00 UTC borró `app-2026-11-15.db` y `-16` y dejó `-17` y `-18`.
- [x] Restauración probada sobre una copia: el procedimiento documentado deja una BD funcional (la API arranca contra ella en un stack temporal o con `DATABASE_URL` apuntando a la copia y `/api/health` responde) sin tocar `data/app.db`.
  - Verificado: `data/backups/app-2026-11-18.db` copiada a una carpeta del scratchpad y montada como `/data` en un contenedor `traductor-backend` aparte (UID 1000, puerto 8765): `alembic upgrade head` + uvicorn, `/api/health` → `{"ok":true}`, integrity `ok`, 192 páginas, 3345 segmentos, cabeza `f3b5d7e9a1c4`; `data/app.db` sin tocar.
- [x] La purga se ejecuta sola según lo programado (log del servicio con el resumen de `purge`), sin cron en el host.
  - Verificado: `docker compose logs backup` al arrancar el servicio (bucle `backup loop`, sin copia del día): `purga: auth_sessions: 0 borradas, auth_rate_limits: 4 borradas, auth_security_events: 0 borradas` y `próxima ejecución: 2026-11-19 03:00 UTC`; la ejecución programada se observó en el contenedor de prueba con `BACKUP_HOUR=5` (log `2026-11-18T05:00:00Z copia … retención … purga …`).
- [x] El README documenta copia, restauración, retención y purga.
  - Verificado: sección «Copias de seguridad y purga (servicio `backup`)» (copia, forzarla, retención, qué no cubre, restauración con `active-jobs` y parada de api/worker/backup, prueba en contenedor aparte); `BACKUP_KEEP`/`BACKUP_HOUR` en la tabla de Configuración y en `.env.example`; la purga ya no remite a un cron.

## Comprobaciones comunes

- [x] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
  - Verificado: `docker compose -f docker-compose.yml -f compose.dev.yml run --rm backend-test` → ruff `All checks passed!`, `194 passed, 1 skipped, 5 deselected`.
- [x] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
  - Verificado: no se tocó `frontend/`.
- [x] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
  - Verificado: ambos `config -q` sin errores.
- [x] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
  - Verificado: `active-jobs` → «sin trabajos activos», `docker compose up -d --build`; `ps`: api, frontend, seaweedfs healthy; worker, backup, cdn Up; `/api/health` → `{"ok":true}`; `/login` → 200.
- [x] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
  - Verificado: lectura `mode=ro` de `data/app.db`: pages 192, segments 3345; mismas filas por tabla que `data/app.db.bak-docker06` salvo `auth_rate_limits` 4 → 0 (ventanas vencidas borradas por la purga, como se espera).
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
  - Pendiente de verificación manual: login, Inicio, revisión del libro #1 y Configuración en http://localhost:3100 (sin cuentas QA autorizadas); `/login` sirve 200 y la API está sana.
