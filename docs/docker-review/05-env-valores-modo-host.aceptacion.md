# 05 · Aceptación: `.env` y `.env.example` mezclan valores del modo host con los de Docker

Ficha: [05-env-valores-modo-host.md](05-env-valores-modo-host.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `.env.example` no contiene `DATABASE_URL`, `DATA_DIR` ni `S3_ENDPOINT` del modo host fuera de un bloque claramente marcado «solo sin Docker».
- [ ] `cp .env.example /tmp/x.env` + `docker compose --env-file /tmp/x.env config -q` funciona y los valores efectivos (`config`) son los de Docker.
- [ ] El README describe las variables que el usuario configura y en qué modo aplica cada una.
- [ ] Ningún secreto en archivos versionados (`git grep -nE 'sk-[A-Za-z0-9]{10,}'` vacío).

## Comprobaciones comunes

- [ ] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
- [ ] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
- [ ] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
- [ ] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
- [ ] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
