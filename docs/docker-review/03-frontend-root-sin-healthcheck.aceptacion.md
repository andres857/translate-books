# 03 · Aceptación: El contenedor del frontend corre como root y sin healthcheck

Ficha: [03-frontend-root-sin-healthcheck.md](03-frontend-root-sin-healthcheck.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `docker compose exec frontend id` → `uid=1000(node)` (no root).
  - Verificado: tras el deploy, `uid=1000(node) gid=1000(node) groups=1000(node)` (antes `uid=0(root)`).
- [x] `docker compose ps frontend` muestra `(healthy)` tras el arranque; parando el proceso a propósito (o con un healthcheck fallido simulado) pasa a `unhealthy` (anotar cómo se comprobó).
  - Verificado: `Up 56 seconds (healthy)`. Fallo simulado sin tocar el stack: `docker run -d --rm --name fe-hc-test --health-interval=2s --health-retries=3 traductor_libros-frontend sleep 120` (misma imagen, sin Next) → `unhealthy`, log `wget: can't connect to remote host (127.0.0.1): Connection refused`; contenedor de prueba borrado.
- [ ] `http://localhost:3100/login` → 200 y el login funciona igual (smoke manual o `npm run test:e2e` si hay credenciales autorizadas; si no, «Pendiente…»).
  - Verificado en parte: `/login` → 200 y `/` → 307 a `/login`.
  - Pendiente de verificación manual: iniciar sesión (no hay cuentas autorizadas).

## Comprobaciones comunes

- [x] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
  - Verificado (host `.venv`): `All checks passed!`; `190 passed, 1 skipped, 5 deselected`.
- [x] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
  - Verificado: solo cambió `frontend/Dockerfile`; tsc y lint sin errores, 20 tests passed, `Problemas: 0`; `npm run build` en verde dentro del `docker compose build`.
- [x] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
  - Verificado: sin salida de error (#01 aún no existe).
- [x] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
  - Verificado: `docker compose up -d --build --no-deps frontend` (api/worker sin reiniciar; `active-jobs`: sin trabajos activos); api, seaweedfs y frontend `healthy`, worker y cdn `Up`; `{"ok":true}`; `/login` 200. Imagen: 336 MB (sin cambio).
- [x] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
  - Verificado: lectura `mode=ro`: pages 192, segments 3345, users 4, glossary 149 (mismas filas por tabla que antes del deploy).
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
  - Pendiente de verificación manual: requiere sesión (no hay cuentas autorizadas).
