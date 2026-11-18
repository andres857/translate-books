---
name: deploy
description: Reconstruye y reinicia los contenedores Docker de traductor_libros (frontend en localhost:3100, api en :8000, worker) para que los cambios de código se vean en la app. Úsala siempre después de cambiar código del frontend o backend, antes de decir al usuario que mire la página, y cuando pida "deploy", "recompila", "reconstruye" o "no veo los cambios".
---

# Deploy local de traductor_libros

La app que el usuario mira (`http://localhost:3100`) es un **build de producción dentro de Docker**,
no un servidor de desarrollo: editar archivos no cambia nada hasta reconstruir la imagen.

Servicios (`docker-compose.yml`, puertos en `.env`):
- `frontend`: Next.js, `WEB_PORT=3100` → contenedor `traductor_libros-frontend-1`.
- `api`: FastAPI, `API_PORT=8000`; aplica `alembic upgrade head` al arrancar. Construye la imagen `traductor-backend`.
- `worker`: usa la misma imagen `traductor-backend`; ejecuta los trabajos de traducción.

Ejecuta todo desde la raíz del repo (`traductor_libros/`).

## 1. Verificar antes de construir

Se ejecuta en contenedor, con los servicios `backend-test`/`frontend-test` de `compose.dev.yml` (perfil `tools`,
imágenes `dev` con el código montado; no montan `data/` ni leen `.env`, así que nunca tocan `data/app.db`):

```bash
DC="docker compose -f docker-compose.yml -f compose.dev.yml"
```

- Backend cambiado: `$DC run --rm backend-test` → `ruff check app tests` (`All checks passed!`) y
  `python -m pytest -q -m "not slow and not s3"` (todo en verde; incluye `test_alembic_check`, que falla si los
  modelos y las migraciones divergen). Sueltos: `$DC run --rm backend-test ruff check app tests`, `… python -m pytest …`.
- Frontend cambiado: `$DC run --rm frontend-test` → `tsc --noEmit`, `npm run lint` (0 errores), `npm run test`,
  `npm run build` y `node ../handoff/check.mjs app lib` (0 problemas). Sueltos: `$DC run --rm frontend-test npm run lint`.
  El smoke test de navegador (`npm run test:e2e`) se ejecuta después de desplegar, con
  `E2E_USER_EMAIL`/`E2E_USER_PASSWORD` de una cuenta `user`.
- Si cambió `backend/pyproject.toml`, `backend/constraints.txt` o `frontend/package.json`: añade `--build` al `run` (reconstruye la imagen `dev`).

Alternativa en el host, si ya existe el entorno local (opcional): `cd backend && .venv/bin/ruff check app tests &&
.venv/bin/python -m pytest -q -m "not slow and not s3"`; `cd frontend && npx tsc --noEmit && npm run lint && npm run test`.

Si algo falla, corrige antes de desplegar.

## 2. Elegir qué reconstruir

| Cambió | Comando |
|---|---|
| Solo `frontend/` | `docker compose up -d --build --no-deps frontend` |
| `backend/` (código, migraciones, Dockerfile) | ver paso 3, luego `docker compose up -d --build --no-deps api worker` |
| Ambos o `docker-compose.yml` | paso 3, luego `docker compose up -d --build` |

Usa `timeout` largo (hasta 600000 ms): el build de Next tarda.

## 3. Antes de reiniciar el backend: no cortar trabajos en curso

Reiniciar `worker` interrumpe una traducción en marcha. Comprueba primero:

```bash
# la API exige sesión: se consulta la BD desde el contenedor
docker compose exec -T api python -m app.cli active-jobs
```

Si hay trabajos activos, no reinicies `worker` sin preguntar al usuario (el frontend sí se puede reconstruir).

## 4. Comprobar que el cambio se sirve

```bash
docker compose ps
curl -fsS localhost:8000/api/health
# sin sesión "/" redirige al login; /login sirve el mismo CSS
css=$(curl -s localhost:3100/login | grep -o '/_next/static/[^"]*\.css' | head -1); curl -s "localhost:3100$css" | grep -c '<selector o variable nueva>'
```

Busca en el CSS/JS servido algo concreto que introdujo el cambio (una variable, un selector, un texto).
Si el build falla, muestra las últimas líneas de `docker compose logs --tail 50 <servicio>`.

## 5. Informar

Di qué servicios se reconstruyeron, que el cambio está servido (con la evidencia del paso 4) y
recuerda al usuario recargar con **Ctrl+Shift+R** (caché del navegador). No digas "ya se ve" sin haber
hecho el paso 4.
