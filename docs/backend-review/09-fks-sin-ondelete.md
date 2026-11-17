# 09 · Las FK no definen qué pasa al borrar y el borrado de un libro carga todo en memoria

- **Severidad:** Medio
- **Categoría:** Integridad del esquema
- **Estado:** resuelto · commit(s) `0b140d9`
- **Ubicación:** `backend/app/db/models.py:40` (jobs.document_id), `:67` (pages.job_id), `:88` (segments.page_id), `:120` y `:129` (document_id de términos y glosario), `:161`, `:185-186` (Playground); `backend/app/playground.py:511-536` (`delete_job`)
- **Aceptación:** [09-fks-sin-ondelete.aceptacion.md](09-fks-sin-ondelete.aceptacion.md)

## Problema

Ninguna FK salvo `auth_sessions.user_id` declara `ondelete`. La cascada pages → segments solo existe en el ORM
(`cascade="all, delete-orphan"` sin `passive_deletes`): al borrar un trabajo, SQLAlchemy **carga cada página y
cada bloque** y emite un DELETE por fila. `glossary.document_id` y `protected_terms.document_id` no tienen índice
(se filtran por él en cada traducción y en `effective_glossary`).

## Cómo reproducirlo

Con `count_queries`: borrar el libro de prueba (`DELETE /api/jobs/{id}`) y contar; en la BD real serían
~3.500 DELETE (3345 bloques + 192 páginas). `sqlite3 data/app.db ".indexes glossary"` → sin índice en
`document_id`.

## Impacto

Borrar un libro grande es lento y retiene el bloqueo de escritura de SQLite (el worker se para); un borrado por SQL directo falla por las FK en lugar de seguir una política clara.

## Corrección propuesta

Migración (con confirmación del usuario): `ON DELETE CASCADE` en pages.job_id, segments.page_id y playground_attempts.run_id; `RESTRICT` explícito en jobs.document_id y jobs.owner_id; índices en `glossary.document_id` y `protected_terms.document_id`; en el ORM `passive_deletes=True`. En SQLite exige reconstruir tablas (`batch_alter_table` con `PRAGMA foreign_keys=OFF` durante la migración — en la del login falló sin ello).

## Notas

Decisión pendiente (preguntar): confirmar la política propuesta. Antes de migrar, comprobar huérfanos (`PRAGMA foreign_key_check` hoy vacío).

Cierre (17-nov-2026), política autorizada por el usuario y decisiones con la opción recomendada:

- **Huérfanos:** ninguno en la copia de la BD real (pages, segments, jobs→documents/users, evaluaciones, intentos,
  glosario y términos; tampoco intentos con `job_id` distinto del de su evaluación). `foreign_key_check` vacío.
- **`playground_runs.job_id` y `playground_attempts.job_id`: RESTRICT**, no CASCADE. `delete_job` ya los borra
  antes que el trabajo porque necesita sus rutas en disco (carpeta de la evaluación y PDF de cada intento); con
  CASCADE un borrado por SQL directo dejaría esos archivos sin referencia. Con RESTRICT ese borrado falla y obliga
  a pasar por `delete_job`. `playground_attempts.run_id` sí es CASCADE (el intento no vive sin su evaluación).
- **glossary/protected_terms.document_id:** solo índice (`ix_*_document_id`); la FK queda sin ON DELETE porque la
  ficha no lo pide y `delete_job` borra esas filas antes que el documento.
- **Migración `f3b5d7e9a1c4`:** `batch_alter_table(recreate="always")` sobre jobs, pages, segments,
  playground_runs y playground_attempts, con una `naming_convention` para poder quitar las FK sin nombre (en la BD
  quedan con nombre `fk_<tabla>_<columna>_<referida>`; `alembic check` lo acepta). La reconstrucción conserva
  índices, `UNIQUE(job_id, number)`, el único de #10 en segments y los `DEFAULT`; los índices de expresión de
  glosario y términos no se tocan (esas tablas no se reconstruyen). `users` tampoco se reconstruye (el CHECK sigue).
  `downgrade()` reconstruye con las FK sin ON DELETE (mismo contenido; el DDL difiere solo en nombres de FK).
- **`alembic/env.py`:** `PRAGMA foreign_keys=OFF` + commit **antes** de abrir la transacción (dentro no tiene
  efecto; por eso falló el batch de la migración del login), `PRAGMA foreign_key_check` vacío antes de confirmar
  (si no, la migración falla) y `foreign_keys=ON` de nuevo al terminar, porque la conexión vuelve al pool.
- **ORM:** `passive_deletes=True` en `Job.pages` y `Page.segments`. `PlaygroundRun` no tiene relación con sus
  intentos en el ORM, así que no aplica. El worker (`save_results`) también se beneficia: al sustituir páginas ya
  no carga sus bloques.
- **Deploy:** se paró el worker, arrancó `api` (que migra al iniciar) y después el worker, para que el worker no
  consultara `jobs` en mitad de la reconstrucción. Copia previa: `data/app.db.bak-review09`.
- Fuera de alcance → #20: `delete_job` sigue borrando fila a fila el glosario, los términos y los intentos.
