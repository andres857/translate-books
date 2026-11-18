# Revisión de contenedores (noviembre 2026)

Objetivo: que todo (frontend, backend, worker y la base de datos SQLite junto al backend) se desarrolle, pruebe y
ejecute solo con Docker, ahora que la traducción ya no usa la suscripción de Claude. Decisiones del usuario: **SQLite
se queda junto al back** (sin PostgreSQL); alcance: desarrollo con recarga, tests y lint en contenedor, endurecer
producción y limpiar restos de la suscripción.

## Línea base (17 de noviembre de 2026)

- `docker-compose.yml`: `api` y `worker` (imagen `traductor-backend`, 2,45 GB: Python 3.12 + Tesseract, OCRmyPDF,
  Calibre, fuentes Noto; usuario sin privilegios; healthcheck), `frontend` (Next 16 `standalone`, 336 MB, sin
  `USER` ni healthcheck), `seaweedfs` + `storage-init` + `cdn` (S3 local).
- BD: SQLite (WAL) en `./data/app.db`, bind mount compartido por `api` y `worker`; cabeza de migraciones
  `f3b5d7e9a1c4`. Libro #1: 192 páginas, 3345 bloques.
- Desarrollo y tests: en el host (`backend/.venv`, `npm`). Backend: 190 passed, 1 skipped; ruff limpio. Frontend: tsc,
  lint, 20 tests y build en verde.
- Puertos (`.env`): web 3100, api 8000, S3 8333, CDN 8090.

## Problemas

| # | Severidad | Problema | Aceptación | Estado |
|---|---|---|---|---|
| 01 | Medio | [Desarrollar exige Python y Node en el equipo](01-compose-dev-recarga.md) | [criterios](01-compose-dev-recarga.aceptacion.md) | resuelto |
| 02 | Medio | [Tests y lint solo corren con herramientas del host](02-tests-lint-en-contenedor.md) | [criterios](02-tests-lint-en-contenedor.aceptacion.md) | resuelto |
| 03 | Medio | [El contenedor del frontend corre como root y sin healthcheck](03-frontend-root-sin-healthcheck.md) | [criterios](03-frontend-root-sin-healthcheck.aceptacion.md) | resuelto |
| 04 | Medio | [La imagen del backend instala dependencias sin versiones fijadas](04-dependencias-backend-sin-fijar.md) | [criterios](04-dependencias-backend-sin-fijar.aceptacion.md) | resuelto |
| 05 | Bajo | [`.env` y `.env.example` mezclan valores del modo host con los de Docker](05-env-valores-modo-host.md) | [criterios](05-env-valores-modo-host.aceptacion.md) | resuelto |
| 06 | Alto | [Sin copias de seguridad de SQLite ni purga programada](06-datos-copias-purga.md) | [criterios](06-datos-copias-purga.aceptacion.md) | resuelto |
| 07 | Bajo | [Quedan restos del modo de suscripción de Claude retirado](07-restos-suscripcion.md) | [criterios](07-restos-suscripcion.aceptacion.md) | resuelto |

## Orden recomendado

1. #07 (limpieza pequeña) y #03 (frontend sin root).
2. #01 (stack de desarrollo) y #02 (tests y lint en contenedor, reutiliza el stage `dev`).
3. #04 (versiones fijadas; se verifica con los tests en contenedor de #02).
4. #05 (`.env`) y #06 (copias y purga; toca datos: con copia previa).

Versiones fijadas del backend (#04): sección «Versiones fijadas del backend» del [README del repo](../../README.md).

## Comportamientos de regresión

- Stack de producción con la skill `deploy`: login, Inicio, revisión del libro #1, Configuración (sin guardar),
  Playground (lista), descargas del libro #1.
- `data/app.db` intacta (mismas filas por tabla); trabajos en curso nunca se interrumpen sin comprobar `active-jobs`.
- No se gasta DeepSeek ni se cambian los ajustes globales.

## Estado final (18 de noviembre de 2026)

Las 7 fichas están resueltas (`git log --oneline --grep "docker-review #"`):

| # | Ficha | Commit del cambio | Commits de docs / estado | Estado |
|---|---|---|---|---|
| 01 | Stack de desarrollo con recarga (`compose.dev.yml`) | `aa65741` | `d4eaf78` | resuelto |
| 02 | Tests y lint en contenedor (`backend-test`, `frontend-test`) | `dd60b32` | `5c72bfd` | resuelto |
| 03 | Frontend sin root (`USER node`) y con healthcheck | `fb52dad` | `4d1d7f5` | resuelto |
| 04 | Versiones fijadas del backend (`backend/constraints.txt`) | `7083dd7` | `18f4eff`, `24e7de6` | resuelto |
| 05 | `.env.example` solo con valores de Docker y modo por variable | `42b0b22` | `64cfc81` | resuelto |
| 06 | Servicio `backup`: copia diaria consistente, retención y purga | `8cffa4b` | `f72efd6` | resuelto |
| 07 | Restos del modo de suscripción de Claude retirados | `151bd02` | `9b16be4` | resuelto |

### Comandos (detalle en el [README del repo](../../README.md))

- **Producción**: `docker compose up -d --build` (o la skill `deploy`); `docker compose ps` → `api` y `frontend`
  healthy, `worker`, `backup`, `cdn` y `seaweedfs` arriba, `storage-init` termina con 0. Antes de reiniciar
  `api`/`worker`: `docker compose exec -T api python -m app.cli active-jobs`.
- **Desarrollo** ([«Desarrollo con Docker»](../../README.md#desarrollo-con-docker-recarga-en-caliente)): con
  `active-jobs` vacío, `docker compose down` y `docker compose -f docker-compose.yml -f compose.dev.yml up -d --build`;
  volver con `… -f compose.dev.yml down` y `docker compose up -d --build`. No conviven con producción.
- **Tests y lint** ([«Tests y lint en contenedor»](../../README.md#tests-y-lint-en-contenedor)):
  `DC="docker compose -f docker-compose.yml -f compose.dev.yml"`; `$DC run --rm backend-test` (ruff + pytest) y
  `$DC run --rm frontend-test` (tsc, lint, vitest, build, `check.mjs`); `--build` tras cambiar dependencias.
- **Copia** ([«Copias de seguridad y purga»](../../README.md#copias-de-seguridad-y-purga-servicio-backup)): diaria
  en el servicio `backup`; a mano `docker compose run --rm backup python -m app.cli backup once`.
- **Restauración**: `active-jobs` vacío, `docker compose stop backup worker api`, apartar `data/app.db` con su
  `-wal`/`-shm`, copiar `data/backups/app-AAAA-MM-DD.db` a `data/app.db`, `docker compose up -d` y comprobar
  `/api/health`; prueba sin tocar la BD en un contenedor aparte (puerto 8765), según el README del repo.

### Tamaños de imagen (`docker images`)

| Imagen | Línea base (17 nov) | Final (18 nov) |
|---|---|---|
| `traductor-backend:latest` (api, worker, backup) | 2,45 GB | 2,45 GB |
| `traductor_libros-frontend:latest` | 336 MB | 336 MB |
| `traductor-backend:dev` (stack dev y `backend-test`) | — | 2,51 GB |
| `traductor-frontend:dev` (stack dev y `frontend-test`) | — | 1,41 GB |

`traductor-test-frontend:latest` (335 MB, de hace 6 días) no la crea este repo ni esta revisión; se deja como estaba.

### Comprobaciones del cierre (18 nov)

- Producción: `docker compose ps` sano (`api` y `frontend` healthy; `worker`, `backup`, `cdn`, `seaweedfs` arriba;
  `storage-init` Exited (0)), antes del cierre y otra vez al volver de dev.
- `backend-test`: `ruff check app tests` → All checks passed!; pytest → 194 passed, 1 skipped, 5 deselected.
  `frontend-test`: exit 0 (tsc sin errores, lint limpio, 20 tests en 3 archivos, `next build` correcto,
  `check.mjs`: 59 archivos, 0 problemas). sha256 de `data/app.db` igual antes y después de ambos (`59034864…`).
- Desarrollo: `config -q` → exit 0; con `active-jobs` vacío se bajó producción, el stack dev levantó
  (`api` healthy) y `/login` → 200, `/api/health` → `{"ok":true}`; luego se volvió a producción con
  `docker compose up -d --build`. Tras ese reinicio el hash de `data/app.db` cambió (checkpoint del WAL al parar),
  pero las filas de todas las tablas coinciden con las de la copia del día.
- Copia: `backup once` → `copia: /data/backups/app-2026-11-18.db (25.3 MB, integrity_check ok)`, purga con 0 filas
  borradas; `PRAGMA integrity_check` desde el host sobre la copia → ok.
- Sin sesión: `:8000/api/health` → `{"ok":true}`; `:3100/login` → 200; por `:3100`, `/api/jobs`, `/api/settings`,
  `/api/users` y `/api/admin/jobs/1/summary` → 401.
- Libro #1 (solo lectura): 192 páginas, 3345 bloques; cabeza de migraciones `f3b5d7e9a1c4`.

### Pendiente de verificación manual

No hay cuentas QA autorizadas, así que lo que exige sesión queda para el usuario en http://localhost:3100:

- Login (#03): iniciar sesión funciona igual que antes (o `npm run test:e2e` con una cuenta `user`).
- Regresión con sesión (#01, #03, #04, #05, #06): Inicio, revisión del libro #1 y Configuración (sin guardar).
- Admin (#07): Configuración muestra el método actual y Playground → Historial se abre.
