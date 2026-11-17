# 17 · El CHECK del rol existe en la BD pero no en el modelo

- **Severidad:** Bajo
- **Categoría:** Divergencia modelo / esquema
- **Estado:** resuelto · commit(s) `36a622f`
- **Ubicación:** `backend/app/db/models.py:216-228` (`User`) frente a `backend/alembic/versions/d2e4f6a8c0b1_auth_rbac.py`
- **Aceptación:** [17-check-rol-solo-en-migracion.aceptacion.md](17-check-rol-solo-en-migracion.aceptacion.md)

## Problema

La migración del login crea `CONSTRAINT ck_users_role CHECK (role IN ('admin','user'))`, pero el modelo no lo
declara. Una BD creada con `Base.metadata.create_all` (p. ej. en un test) no tendría la restricción, y no hay
`naming_convention` para que los nombres de constraints futuros sean estables.

## Cómo reproducirlo

`sqlite3 data/app.db '.schema users'` muestra el CHECK; `Base.metadata.tables['users'].constraints` no lo incluye.

## Impacto

Bajo: hoy todas las BD se crean con Alembic. Riesgo de que una migración autogenerada futura lo elimine.

## Corrección propuesta

Declarar `CheckConstraint("role IN ('admin','user')", name="ck_users_role")` en `__table_args__` y añadir `naming_convention` al `MetaData` de `Base` (sin renombrar constraints existentes).

## Notas

- El CHECK se declara con `name="role"`: la convención `"ck": "ck_%(table_name)s_%(constraint_name)s"` lo deja en
  `ck_users_role`, el mismo nombre que crea la migración `d2e4f6a8c0b1`. Pasar `name="ck_users_role"` con esa
  convención daría `ck_users_ck_users_role`.
- La `naming_convention` de `Base` coincide con los nombres actuales (índices `ix_<tabla>_<columna>`, FK
  `fk_<tabla>_<columna>_<tabla referida>` de la migración `f3b5d7e9a1c4`, `uq_<tabla>_<columna>`, `pk_<tabla>`).
  Los UNIQUE de `users.email`, `auth_sessions.token_hash` y `files.key`, la FK de `auth_sessions` y las PK siguen
  sin nombre en SQLite; `alembic check` no los compara por nombre, así que no hay diferencias ni migración. Si una
  migración futura los reconstruye con `batch_alter_table`, recibirán el nombre de la convención.
- `alembic check` no compara CHECK constraints: el test de `create_all` es lo que protege que el modelo los declare.
