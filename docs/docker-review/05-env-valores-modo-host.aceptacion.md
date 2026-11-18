# 05 · Aceptación: `.env` y `.env.example` mezclan valores del modo host con los de Docker

Ficha: [05-env-valores-modo-host.md](05-env-valores-modo-host.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `.env.example` no contiene `DATABASE_URL`, `DATA_DIR` ni `S3_ENDPOINT` del modo host fuera de un bloque claramente marcado «solo sin Docker».
  - Verificado: `grep -nE '^(DATABASE_URL|DATA_DIR|S3_ENDPOINT|CORS_ORIGINS)=' .env.example` vacío; solo aparecen comentados en el bloque final «Solo sin Docker».
- [x] `cp .env.example /tmp/x.env` + `docker compose --env-file /tmp/x.env config -q` funciona y los valores efectivos (`config`) son los de Docker.
  - Verificado: copia en el scratchpad; `config -q` (y con `compose.dev.yml`) sin error; en `api`/`worker`/`storage-init`: `DATABASE_URL=sqlite:////data/app.db`, `DATA_DIR=/data`, `S3_ENDPOINT=http://seaweedfs:8333`, `CORS_ORIGINS=http://localhost:3000` (= `WEB_PORT`), `S3_PUBLIC_ENDPOINT=http://localhost:8333`.
- [x] El README describe las variables que el usuario configura y en qué modo aplica cada una.
  - Verificado: tabla «Configuración (`.env`)» con columna Modo (Docker / ambos / sin Docker) para todas las variables de `.env.example`, más el aviso en «Desarrollo local (sin Docker)».
- [x] Ningún secreto en archivos versionados (`git grep -nE 'sk-[A-Za-z0-9]{10,}'` vacío).
  - Verificado: `git grep -nE 'sk-[A-Za-z0-9]{10,}'` sin resultados (rc=1); `.env` sigue fuera de git.

## Comprobaciones comunes

- [x] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
  - Verificado: en contenedor (`backend-test`), `All checks passed!` y `190 passed, 1 skipped, 5 deselected`.
- [x] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
  - Verificado: no se tocó `frontend/` (solo `.env.example`, `README.md` y docs); no aplica.
- [x] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
  - Verificado: ambos sin salida ni error (con el `.env` local y con la copia de `.env.example`).
- [x] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
  - Verificado: sin cambios de código ni de compose no hay imagen que reconstruir; `active-jobs` → «sin trabajos activos»; `docker compose up -d` no recreó `api`/`worker`; `api`, `frontend`, `seaweedfs` healthy, `worker` y `cdn` Up; health `{"ok":true}`; `/login` 200.
- [x] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
  - Verificado: recuento en solo lectura (`mode=ro`): libro #1 con 192 páginas y 3345 segmentos; `jobs 1`, `users 4`, `translation_cache 2141`, `glossary 149` (mismos valores que en #04).
- [ ] Regresión: login en http://localhost:3100, ver Inicio, abrir la revisión del libro #1 y Configuración (sin guardar).
  - Pendiente de verificación manual: requiere sesión (cuentas QA no autorizadas); sin sesión `/login` responde 200 y la API está sana.
