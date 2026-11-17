# 09 · Las FK no definen qué pasa al borrar y el borrado de un libro carga todo en memoria

- **Severidad:** Medio
- **Categoría:** Integridad del esquema
- **Estado:** abierto
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
