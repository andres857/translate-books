# 01 · Aceptación: Desarrollar exige Python y Node en el equipo

Ficha: [01-compose-dev-recarga.md](01-compose-dev-recarga.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Con el stack dev arriba, editar un texto visible de un componente de `frontend/app` se ve en http://localhost:3100 en < 10 s sin rebuild (anotar el cambio y el tiempo; revertirlo después).
- [ ] Editar un handler de `backend/app/api` (p. ej. añadir temporalmente un campo a `/api/health` con sesión o un log) se refleja sin rebuild gracias a `--reload` (anotar y revertir).
- [ ] El worker del stack dev usa el código montado: tras `docker compose … restart worker` (o recarga automática) ejecuta el código editado (evidencia en logs).
- [ ] En el stack dev no se usa ningún binario del host: `which python3 node` no es necesario (los comandos documentados empiezan por `docker compose`).
- [ ] Volver a producción con la skill `deploy` deja el stack de producción como antes (imágenes de producción, `next start`/`server.js`).

## Comprobaciones comunes

- [ ] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
- [ ] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
- [ ] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
- [ ] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
- [ ] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
