# 13 · Borrado duplicado, imports internos y consultas al estilo 1.x

- **Severidad:** Medio
- **Categoría:** Estructura y mantenibilidad
- **Estado:** resuelto · commits `12b75fa`, `26f2832`
- **Ubicación:** `backend/app/api/routes_jobs.py:381-401` ≈ `backend/app/api/routes_playground.py:99-113`; `routes_admin.py:15` (importa `_job_or_404` privado); `db.query(` en `routes_jobs.py:330,488`, `routes_terms.py`, `worker.py:70`, `files_service.py:86`
- **Aceptación:** [13-logica-duplicada-y-legacy.aceptacion.md](13-logica-duplicada-y-legacy.aceptacion.md)

## Problema

- `delete_job` y `delete_book` repiten la comprobación de «evaluación en curso», el borrado y la limpieza de
  archivos.
- `delete_job` importa `select`, `func`, `playground` y `PlaygroundRun` **dentro** de la función.
- `routes_admin` y otras rutas importan `_job_or_404` (con guion bajo, privado) de `routes_jobs`.
- Conviven `db.query(...)` (API 1.x heredada) y `select(...)` (2.x).

## Cómo reproducirlo

`grep -rn "\.query(" backend/app` → ocurrencias en rutas, worker y servicios.

## Impacto

Cambios en una ruta de borrado que no llegan a la otra; reglas de acceso repartidas entre routers.

## Corrección propuesta

Un módulo `app/jobs_service.py` con `get_visible_job` (público), `ensure_not_busy` y `delete_job_and_files`; las dos rutas lo llaman. Pasar `db.query` a `select()`. Sin cambiar rutas ni respuestas.

## Notas

Es un refactor: no mezclar con cambios de comportamiento.

Plan (decidido por el coordinador con la autorización del usuario, 17-nov-2026; refactor puro: sin cambios de
rutas, respuestas ni mensajes):

- Módulo nuevo `backend/app/jobs_service.py`:
  - `get_visible_job(db, job_id, principal | None)`: sustituye a `_job_or_404` y `can_see` de `routes_jobs`
    (mismo 404 «No encontramos ese trabajo.»; `None` solo desde routers que ya exigen admin). `routes_jobs` y
    `routes_admin` lo importan de aquí.
  - `ensure_not_busy(db, job, playground_busy=...)`: 409 si el trabajo está «queued/running» y 409 si hay una
    evaluación del Playground en curso con él. Los mensajes de esa evaluación difieren entre las dos rutas, así
    que el mensaje es un parámetro (por defecto el de `DELETE /api/jobs/{id}`; el Playground pasa el suyo).
  - `delete_job_and_files(db, job)`: `pg.delete_job` + `commit` + `pg.remove_path` de cada ruta después del
    commit.
- `DELETE /api/jobs/{id}` y `DELETE /api/admin/playground/books/{id}` llaman a `ensure_not_busy` y
  `delete_job_and_files`; cada una conserva su comprobación previa (`get_visible_job` / `_job_done`). En el
  Playground la comprobación de «queued/running» no cambia nada: `_job_done` ya exige `status == "done"`.
- `delete_job` deja de importar dentro de la función. No quedan imports dentro de funciones en `jobs_service`
  ni en las rutas tocadas, salvo los perezosos ya existentes que no forman parte de esta ficha (ver abajo).
- Todas las `.query(` de `backend/app` pasan a `select()` con los mismos resultados: `routes_jobs` (lista y
  páginas), `routes_terms` (términos y glosario), `worker.save_results`, `files_service.confirm`,
  `auth.sessions.find` y `cli.cmd_active_jobs`.
- Dos commits de código: servicio de borrado y `select()`.
- Fuera de alcance: el borrado del glosario fila a fila (#20).

Decisiones al implementar: `can_see` pasa a `_can_see`, privado de `jobs_service` (solo lo usa
`get_visible_job`). Imports dentro de funciones: no queda ninguno en `jobs_service` ni en `routes_jobs`; los que
siguen en `backend/app` no son de esta ficha y se dejan: `cli.py` (perezosos para que cada subcomando cargue solo
lo suyo; `cmd_active_jobs` importa `select` igual que `cmd_auth_recover`), los de dependencias pesadas u
opcionales del pipeline (`numpy`, `cv2`, `pytesseract`, `fontTools`, `pymupdf.layout`, el adaptador S3, `pymupdf`
en `routes_admin.book_info`) y los que evitan ciclos: `glossary_service` y `playground` importan
`app.worker.friendly_error` dentro de la función porque `worker` importa ambos módulos; `glossary_service`
importa `app.playground.to_segments` dentro porque `playground` importa `glossary_service`. Quedan además, sin
ciclo, los perezosos de `runtime_settings` (traductores) y de `glossary_service._discover` (`runtime_settings`,
`pipeline.runner`, `pipeline.translate`), que cargan el pipeline solo cuando se usa; subirlos es un cambio
aparte, no de esta ficha.
