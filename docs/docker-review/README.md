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
| 01 | Medio | [Desarrollar exige Python y Node en el equipo](01-compose-dev-recarga.md) | [criterios](01-compose-dev-recarga.aceptacion.md) | abierto |
| 02 | Medio | [Tests y lint solo corren con herramientas del host](02-tests-lint-en-contenedor.md) | [criterios](02-tests-lint-en-contenedor.aceptacion.md) | abierto |
| 03 | Medio | [El contenedor del frontend corre como root y sin healthcheck](03-frontend-root-sin-healthcheck.md) | [criterios](03-frontend-root-sin-healthcheck.aceptacion.md) | abierto |
| 04 | Medio | [La imagen del backend instala dependencias sin versiones fijadas](04-dependencias-backend-sin-fijar.md) | [criterios](04-dependencias-backend-sin-fijar.aceptacion.md) | abierto |
| 05 | Bajo | [`.env` y `.env.example` mezclan valores del modo host con los de Docker](05-env-valores-modo-host.md) | [criterios](05-env-valores-modo-host.aceptacion.md) | abierto |
| 06 | Alto | [Sin copias de seguridad de SQLite ni purga programada](06-datos-copias-purga.md) | [criterios](06-datos-copias-purga.aceptacion.md) | abierto |
| 07 | Bajo | [Quedan restos del modo de suscripción de Claude retirado](07-restos-suscripcion.md) | [criterios](07-restos-suscripcion.aceptacion.md) | abierto |

## Orden recomendado

1. #07 (limpieza pequeña) y #03 (frontend sin root).
2. #01 (stack de desarrollo) y #02 (tests y lint en contenedor, reutiliza el stage `dev`).
3. #04 (versiones fijadas; se verifica con los tests en contenedor de #02).
4. #05 (`.env`) y #06 (copias y purga; toca datos: con copia previa).

## Comportamientos de regresión

- Stack de producción con la skill `deploy`: login, Inicio, revisión del libro #1, Configuración (sin guardar),
  Playground (lista), descargas del libro #1.
- `data/app.db` intacta (mismas filas por tabla); trabajos en curso nunca se interrumpen sin comprobar `active-jobs`.
- No se gasta DeepSeek ni se cambian los ajustes globales.
