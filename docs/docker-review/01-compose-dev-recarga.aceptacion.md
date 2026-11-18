# 01 · Aceptación: Desarrollar exige Python y Node en el equipo

Ficha: [01-compose-dev-recarga.md](01-compose-dev-recarga.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Con el stack dev arriba, editar un texto visible de un componente de `frontend/app` se ve en http://localhost:3100 en < 10 s sin rebuild (anotar el cambio y el tiempo; revertirlo después).
  - Verificado: en `frontend/app/login/page.tsx` «…el administrador.» → «…el administrador (dev01).»; `curl localhost:3100/login` lo sirvió a los 0,12 s (`next dev` con Turbopack, sin rebuild); revertido con `git checkout` y comprobado que ya no aparece.
- [x] Editar un handler de `backend/app/api` (p. ej. añadir temporalmente un campo a `/api/health` con sesión o un log) se refleja sin rebuild gracias a `--reload` (anotar y revertir).
  - Verificado: campo temporal `"dev01": true` en la respuesta sin sesión de `/api/health` (`backend/app/main.py`); `curl localhost:8000/api/health` → `{"ok":true,"dev01":true}` a los 1,5 s, log `WatchFiles detected changes in 'app/main.py'. Reloading...`; revertido → `{"ok":true}`.
- [x] El worker del stack dev usa el código montado: tras `docker compose … restart worker` (o recarga automática) ejecuta el código editado (evidencia en logs).
  - Verificado: «Worker iniciado, esperando trabajos...» → «… (dev01)» en `backend/app/worker.py`; `active-jobs` → «sin trabajos activos»; tras `restart worker` el log mostró `Worker iniciado, esperando trabajos... (dev01)`; revertido y reiniciado (log original).
- [x] En el stack dev no se usa ningún binario del host: `which python3 node` no es necesario (los comandos documentados empiezan por `docker compose`).
  - Verificado: README «Desarrollo con Docker (recarga en caliente)»: todos los comandos son `docker compose …`; las imágenes `traductor-backend:dev` y `traductor-frontend:dev` traen Python 3.12, Node 22 y sus dependencias (`node_modules` y `.next` en volúmenes anónimos, sin los del host).
- [x] Volver a producción con la skill `deploy` deja el stack de producción como antes (imágenes de producción, `next start`/`server.js`).
  - Verificado: `… compose.dev.yml down` + `docker compose up -d --build`: `api`/`worker` con imagen `traductor-backend` y comando `alembic upgrade head && uvicorn …` sin `--reload`; `frontend` con `traductor_libros-frontend`, `USER node`, `node server.js` y healthcheck `wget … /login` (`healthy`).

## Comprobaciones comunes

- [x] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
  - Verificado: host `.venv`: `All checks passed!`; `190 passed, 1 skipped, 5 deselected`.
- [x] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
  - Verificado (host): tsc sin errores, eslint sin avisos, 20 tests passed, build correcto, check.mjs «Problemas: 0».
- [x] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
  - Verificado: ambos sin salida y código 0.
- [x] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
  - Verificado: api, frontend y seaweedfs `healthy`, worker y cdn `Up`; `{"ok":true}`; `/login` → 200 y su CSS → 200.
- [x] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
  - Verificado: copia previa `data/app.db.bak-docker01` (API de backup de sqlite3); recuento por tabla idéntico antes y después (pages 192, segments 3345, users 4, jobs 1, translation_cache 2141…), cabeza `f3b5d7e9a1c4`.
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
  - Pendiente de verificación manual: exige sesión y no hay cuentas QA autorizadas; sin sesión `/login` → 200 en producción y en dev, y el rewrite `/api/health` por :3100 respondió `{"ok":true}` en dev.
