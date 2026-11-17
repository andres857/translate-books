# 13 · Aceptación: Borrado duplicado, imports internos y consultas al estilo 1.x

Ficha: [13-logica-duplicada-y-legacy.md](13-logica-duplicada-y-legacy.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] `grep -rn "\.query(" backend/app` no devuelve resultados.
  - Verificado: sin resultados tras `26f2832` (antes: `routes_jobs` ×2, `routes_terms` ×2, `worker`, `files_service`, `auth/sessions`, `cli`); `app.cli active-jobs` sobre una copia de `data/app.db` responde «sin trabajos activos».
- [x] `grep -rn "_job_or_404" backend/app` solo aparece en su módulo (o se ha sustituido por la función pública).
  - Verificado: sin resultados; `routes_jobs` y `routes_admin` usan `app.jobs_service.get_visible_job` (`can_see` pasa a `_can_see`, privado del servicio).
- [x] La lógica de borrado está en un solo sitio: `grep -n "remove_path" backend/app/api/*.py` no aparece en las rutas.
  - Verificado: sin resultados; solo en `app/playground.py` (definición) y `app/jobs_service.py:delete_job_and_files`, que llaman las dos rutas de borrado.
- [x] Todos los tests de borrado y de autorización existentes siguen en verde sin cambiarlos.
  - Verificado: `git diff d53924e..HEAD -- backend/tests` vacío; pasan `test_playground` (409/200/404 de los dos DELETE), `test_admin` (borrado) y `test_auth_matrix` (403 del user).

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 183 passed, 1 skipped, 5 deselected tras cada commit (incluye `test_response_snapshots`).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `.venv/bin/ruff check app tests` → «All checks passed!»; `test_alembic_check` dentro de la suite en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos, `docker compose up -d --build --no-deps api worker`; health `{"ok":true}`, `/login` 200 y `import app.jobs_service` dentro del contenedor.
- [ ] Regresión: borrar un libro desde Inicio (admin) y desde el Playground sigue funcionando.
  - Pendiente de verificación manual: requiere cuenta admin en la app (cuentas QA no autorizadas). Cubierto por los tests de ambos DELETE (`test_playground`, `test_admin`), sin cambios.
