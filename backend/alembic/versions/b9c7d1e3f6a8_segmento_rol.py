"""rol del segmento (campo de ficha de datos)

Revision ID: b9c7d1e3f6a8
Revises: a8b6c0d2e5f7
"""
import sqlalchemy as sa
from alembic import op

revision = 'b9c7d1e3f6a8'
down_revision = 'a8b6c0d2e5f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("segments", sa.Column("role", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("segments", "role")
