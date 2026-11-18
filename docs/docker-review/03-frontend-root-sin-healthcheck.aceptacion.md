# 03 · Aceptación: El contenedor del frontend corre como root y sin healthcheck

Ficha: [03-frontend-root-sin-healthcheck.md](03-frontend-root-sin-healthcheck.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `docker compose exec frontend id` → `uid=1000(node)` (no root).
- [ ] `docker compose ps frontend` muestra `(healthy)` tras el arranque; parando el proceso a propósito (o con un healthcheck fallido simulado) pasa a `unhealthy` (anotar cómo se comprobó).
- [ ] `http://localhost:3100/login` → 200 y el login funciona igual (smoke manual o `npm run test:e2e` si hay credenciales autorizadas; si no, «Pendiente…»).

## Comprobaciones comunes

- [ ] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
- [ ] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
- [ ] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
- [ ] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
- [ ] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
