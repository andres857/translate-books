# 02 · Aceptación: Tests y lint solo corren con herramientas del host

Ficha: [02-tests-lint-en-contenedor.md](02-tests-lint-en-contenedor.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `docker compose … run --rm <servicio> python -m pytest -q -m "not slow and not s3"` → mismo total que en el host (anotar ambos).
  - Verificado: `docker compose -f docker-compose.yml -f compose.dev.yml run --rm backend-test` → `190 passed, 1 skipped, 5 deselected, 1 warning in 56.92s`; host (`backend/.venv`) → `190 passed, 1 skipped, 5 deselected, 1 warning in 54.78s`.
- [x] `docker compose … run --rm <servicio> ruff check app tests` → `All checks passed!`.
  - Verificado: `… run --rm backend-test ruff check app tests` → `All checks passed!` (ruff 0.17.5, pytest 9.2.0, uid 1000 `app`).
- [x] Frontend en contenedor: `tsc --noEmit`, `npm run lint`, `npm run test` y `node ../handoff/check.mjs app lib` en verde (anotar salidas).
  - Verificado: `… run --rm frontend-test` → tsc sin salida (exit 0), `eslint .` sin errores, vitest `3 passed (3)` / `20 passed (20)`, `next build` compilado (13 rutas), check.mjs `Archivos revisados: 59 · Tokens usados: 66 de 86 · Problemas: 0` (`handoff/` montado en `/handoff:ro`).
- [x] Ejecutar los tests en contenedor no modifica `data/app.db` (hash/mtime antes y después) ni crea archivos con dueño root en el repo (`find . -user root` vacío).
  - Verificado: sha256 y mtime de `data/app.db*` idénticos antes y después (`diff` vacío; app.db `5903486…a97`, 22:41:44); `find . -user root` vacío; en `backend-test` no existe `/data` y `DATABASE_URL=sqlite:////app/tests/output/test.db`.
- [x] La skill `deploy` (paso 1) usa los comandos en contenedor y ya no menciona `.venv` como requisito.
  - Verificado: paso 1 usa `$DC run --rm backend-test|frontend-test`; `.venv` solo aparece como alternativa opcional en el host.

## Comprobaciones comunes

- [x] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
  - Verificado: en contenedor, ver arriba (190 passed, ruff limpio).
- [x] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
  - Verificado: no se tocó código del frontend; aun así todo en verde en `frontend-test` (ver arriba).
- [x] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
  - Verificado: ambos sin salida, exit 0.
- [x] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; `docker compose up -d --build`; api/frontend/seaweedfs healthy, cdn y worker Up; `{"ok":true}`; `/login` → 200.
- [x] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
  - Verificado: lectura `mode=ro`: pages 192, segments 3345; recuento por tabla idéntico al de `data/app.db.bak-docker01`.
- [x] Regresión: ninguna funcional.
  - Verificado: el stack de producción (`docker-compose.yml`, Dockerfiles) no cambió; solo `compose.dev.yml` (servicios con perfil `tools`), README y skill.
