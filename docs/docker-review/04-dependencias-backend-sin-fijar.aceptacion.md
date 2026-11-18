# 04 · Aceptación: La imagen del backend instala dependencias sin versiones fijadas

Ficha: [04-dependencias-backend-sin-fijar.md](04-dependencias-backend-sin-fijar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Existe el archivo de versiones fijadas y el Dockerfile lo usa (`grep` en el Dockerfile).
  - Verificado: `backend/constraints.txt` (68 pines `==`: 63 del proyecto + 5 de `[dev]`); `grep -c constraints backend/Dockerfile` → 6 (`COPY pyproject.toml constraints.txt ./` y `pip install --no-cache-dir -c constraints.txt …` en `base` y en `dev`).
- [x] `pip freeze` dentro del contenedor `api` coincide con el archivo fijado (diff vacío salvo el propio paquete del proyecto).
  - Verificado: tras el deploy de `7083dd7`, `docker compose exec -T api pip freeze` y el del `worker` → diff vacío con la sección del proyecto (el paquete no se instala en site-packages, así que no aparece). El `freeze` de `traductor-backend:dev` → diff vacío con el archivo completo (ambas secciones).
- [x] Dos builds seguidos sin caché de la capa de dependencias producen el mismo `pip freeze` (anotar).
  - Verificado: `docker build -t traductor-backend:d04-a backend` (capa de pip nueva por el `COPY` de `constraints.txt`) y `docker build --no-cache -t traductor-backend:d04-b backend` → `pip freeze` idénticos (63 líneas, iguales al archivo), `pip check` sin conflictos; imágenes temporales borradas.
- [x] La suite completa (`-m "not slow and not s3"`) pasa dentro de la imagen construida con las versiones fijadas.
  - Verificado: `docker compose -f docker-compose.yml -f compose.dev.yml run --rm --build backend-test` (imagen `dev` = `base` con las mismas restricciones + `[dev]`) → `All checks passed!` y `190 passed, 1 skipped, 5 deselected`.
- [x] El README explica cómo actualizar las versiones fijadas.
  - Verificado: sección «Versiones fijadas del backend» en `docs/docker-review/README.md` (build sin restricciones, `pip freeze` por secciones, tests en contenedor, comprobación tras el deploy); la cabecera de `constraints.txt` remite a ella.

## Comprobaciones comunes

- [x] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
  - Verificado: en contenedor (`backend-test`), `All checks passed!` y `190 passed, 1 skipped, 5 deselected in 55.51s`.
- [x] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
  - Verificado: no se tocó `frontend/` (`git show --stat 7083dd7`); no aplica.
- [x] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
  - Verificado: ambos sin salida ni error.
- [x] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; `docker compose up -d --build --no-deps api worker`; `api`, `frontend`, `seaweedfs` healthy, `worker` y `cdn` Up; health `{"ok":true}`; `/login` 200.
- [x] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
  - Verificado: recuento por tabla en solo lectura (`mode=ro`) antes y después del deploy, idéntico: `jobs 1`, `pages 192`, `segments 3345`, `users 4`, `translation_cache 2141`… (la BD solo contiene el libro #1).
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
  - Pendiente de verificación manual: requiere sesión (cuentas QA no autorizadas); sin sesión `/login` responde 200 y la API está sana.
