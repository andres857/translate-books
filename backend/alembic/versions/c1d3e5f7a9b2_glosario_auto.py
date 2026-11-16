"""glosario descubierto: origen, categoría y nota; especialidad del libro

Revision ID: c1d3e5f7a9b2
Revises: b9c7d1e3f6a8
"""
import sqlalchemy as sa
from alembic import op

revision = 'c1d3e5f7a9b2'
down_revision = 'b9c7d1e3f6a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("glossary", sa.Column("origin", sa.String(16), nullable=False, server_default="manual"))
    op.add_column("glossary", sa.Column("category", sa.String(32), nullable=True))
    op.add_column("glossary", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("domain", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "domain")
    op.drop_column("glossary", "note")
    op.drop_column("glossary", "category")
    op.drop_column("glossary", "origin")
