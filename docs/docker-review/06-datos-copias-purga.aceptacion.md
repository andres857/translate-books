# 06 · Aceptación: Sin copias de seguridad de SQLite ni purga programada

Ficha: [06-datos-copias-purga.md](06-datos-copias-purga.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Tras forzar una ejecución del servicio de copia, existe `data/backups/app-<fecha>.db` y `PRAGMA integrity_check` → `ok` con las mismas filas por tabla que `data/app.db`.
- [ ] La retención funciona: con más copias de las configuradas, solo quedan las N más recientes (test o prueba con fechas simuladas).
- [ ] Restauración probada sobre una copia: el procedimiento documentado deja una BD funcional (la API arranca contra ella en un stack temporal o con `DATABASE_URL` apuntando a la copia y `/api/health` responde) sin tocar `data/app.db`.
- [ ] La purga se ejecuta sola según lo programado (log del servicio con el resumen de `purge`), sin cron en el host.
- [ ] El README documenta copia, restauración, retención y purga.

## Comprobaciones comunes

- [ ] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
- [ ] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
- [ ] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
- [ ] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
- [ ] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
