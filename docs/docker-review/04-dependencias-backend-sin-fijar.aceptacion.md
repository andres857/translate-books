# 04 · Aceptación: La imagen del backend instala dependencias sin versiones fijadas

Ficha: [04-dependencias-backend-sin-fijar.md](04-dependencias-backend-sin-fijar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Existe el archivo de versiones fijadas y el Dockerfile lo usa (`grep` en el Dockerfile).
- [ ] `pip freeze` dentro del contenedor `api` coincide con el archivo fijado (diff vacío salvo el propio paquete del proyecto).
- [ ] Dos builds seguidos sin caché de la capa de dependencias producen el mismo `pip freeze` (anotar).
- [ ] La suite completa (`-m "not slow and not s3"`) pasa dentro de la imagen construida con las versiones fijadas.
- [ ] El README explica cómo actualizar las versiones fijadas.

## Comprobaciones comunes

- [ ] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
- [ ] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
- [ ] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
- [ ] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
- [ ] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
