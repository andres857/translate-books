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

- Frontend cambiado: `cd frontend && npx tsc --noEmit` y `node ../handoff/check.mjs app lib` (0 problemas).
- Backend cambiado: `cd backend && python -m pytest -q` (o las pruebas afectadas).

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
curl -s localhost:8000/api/jobs | python3 -c "import json,sys; a=[j for j in json.load(sys.stdin) if j['status'] not in ('done','failed','error','cancelled','canceled')]; print(a and [(j['id'],j['status'],j['stage']) for j in a] or 'sin trabajos activos')"
```

Si hay trabajos activos, no reinicies `worker` sin preguntar al usuario (el frontend sí se puede reconstruir).

## 4. Comprobar que el cambio se sirve

```bash
docker compose ps
curl -fsS localhost:8000/api/health
css=$(curl -s localhost:3100/ | grep -o '/_next/static/[^"]*\.css' | head -1); curl -s "localhost:3100$css" | grep -c '<selector o variable nueva>'
```

Busca en el CSS/JS servido algo concreto que introdujo el cambio (una variable, un selector, un texto).
Si el build falla, muestra las últimas líneas de `docker compose logs --tail 50 <servicio>`.

## 5. Informar

Di qué servicios se reconstruyeron, que el cambio está servido (con la evidencia del paso 4) y
recuerda al usuario recargar con **Ctrl+Shift+R** (caché del navegador). No digas "ya se ve" sin haber
hecho el paso 4.
