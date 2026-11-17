"""FK con ON DELETE explícito (CASCADE en los hijos, RESTRICT en las referencias) e índices de document_id

Revision ID: f3b5d7e9a1c4
Revises: e1f3a5c7b9d2
"""
from alembic import op

revision = 'f3b5d7e9a1c4'
down_revision = 'e1f3a5c7b9d2'
branch_labels = None
depends_on = None

# Las FK de estas tablas no tienen nombre: la convención se lo da al reflejarlas para poder quitarlas.
# SQLite no cambia una FK sin reconstruir la tabla (copia → DROP → RENAME, que conserva índices y UNIQUE);
# alembic/env.py desactiva foreign_keys durante la migración para que el DROP no borre en cascada.
NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}

# (tabla, columna, tabla referida, ondelete)
FKS = [
    ("jobs", "document_id", "documents", "RESTRICT"),
    ("jobs", "owner_id", "users", "RESTRICT"),
    ("pages", "job_id", "jobs", "CASCADE"),
    ("segments", "page_id", "pages", "CASCADE"),
    ("playground_runs", "job_id", "jobs", "RESTRICT"),
    ("playground_attempts", "run_id", "playground_runs", "CASCADE"),
    ("playground_attempts", "job_id", "jobs", "RESTRICT"),
]


def _rebuild(ondelete_of) -> None:
    for table in dict.fromkeys(t for t, *_ in FKS):
        with op.batch_alter_table(table, recreate="always", naming_convention=NAMING) as b:
            for t, col, ref, ondelete in FKS:
                if t != table:
                    continue
                name = NAMING["fk"] % {"table_name": t, "column_0_name": col, "referred_table_name": ref}
                b.drop_constraint(name, type_="foreignkey")
                b.create_foreign_key(name, ref, [col], ["id"], ondelete=ondelete_of(ondelete))


def upgrade() -> None:
    _rebuild(lambda ondelete: ondelete)
    op.create_index("ix_glossary_document_id", "glossary", ["document_id"])
    op.create_index("ix_protected_terms_document_id", "protected_terms", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_protected_terms_document_id", "protected_terms")
    op.drop_index("ix_glossary_document_id", "glossary")
    _rebuild(lambda _: None)  # FK sin ON DELETE, como antes
