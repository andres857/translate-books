# 02 · Aceptación: Tests y lint solo corren con herramientas del host

Ficha: [02-tests-lint-en-contenedor.md](02-tests-lint-en-contenedor.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `docker compose … run --rm <servicio> python -m pytest -q -m "not slow and not s3"` → mismo total que en el host (anotar ambos).
- [ ] `docker compose … run --rm <servicio> ruff check app tests` → `All checks passed!`.
- [ ] Frontend en contenedor: `tsc --noEmit`, `npm run lint`, `npm run test` y `node ../handoff/check.mjs app lib` en verde (anotar salidas).
- [ ] Ejecutar los tests en contenedor no modifica `data/app.db` (hash/mtime antes y después) ni crea archivos con dueño root en el repo (`find . -user root` vacío).
- [ ] La skill `deploy` (paso 1) usa los comandos en contenedor y ya no menciona `.venv` como requisito.

## Comprobaciones comunes

- [ ] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
- [ ] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
- [ ] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
- [ ] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
- [ ] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
- [ ] Regresión: ninguna funcional.
