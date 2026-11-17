# 17 · El CHECK del rol existe en la BD pero no en el modelo

- **Severidad:** Bajo
- **Categoría:** Divergencia modelo / esquema
- **Estado:** abierto
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
