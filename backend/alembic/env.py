from alembic import context

from app.db.models import Base
from app.db.session import engine

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=str(engine.url), target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def _foreign_keys(connection, on: bool) -> None:
    # PRAGMA foreign_keys no tiene efecto dentro de una transacción: se ejecuta y se confirma antes de abrirla
    connection.exec_driver_sql(f"PRAGMA foreign_keys={'ON' if on else 'OFF'}")
    connection.commit()


def run_migrations_online():
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        # El engine abre cada conexión con foreign_keys=ON. Una migración que reconstruye tablas (batch_alter_table:
        # crear copia → DROP → RENAME) borraría en cascada o fallaría con ellas activas: se desactivan durante la
        # migración y, antes de confirmarla, `foreign_key_check` debe salir vacío.
        if sqlite:
            _foreign_keys(connection, False)
        try:
            context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
                if sqlite:
                    bad = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                    if bad:
                        raise RuntimeError(f"La migración deja referencias rotas (foreign_key_check): {bad[:10]}")
        finally:
            if sqlite:  # la conexión vuelve al pool: que no quede sin FK
                connection.rollback()
                _foreign_keys(connection, True)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
