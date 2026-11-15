"""playground: alcance (página, páginas, capítulo, libro) y estado para reanudar

Revision ID: d5e3f7a9b2c4
Revises: c4d2e6f8a1b3
"""
import sqlalchemy as sa
from alembic import op

revision = 'd5e3f7a9b2c4'
down_revision = 'c4d2e6f8a1b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("playground_runs") as batch:
        batch.add_column(sa.Column("scope", sa.String(16), nullable=False, server_default="pages"))
        batch.add_column(sa.Column("state", sa.JSON()))
        batch.alter_column("pages", type_=sa.Text(), existing_type=sa.String(32), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("playground_runs") as batch:
        batch.alter_column("pages", type_=sa.String(32), existing_type=sa.Text(), existing_nullable=False)
        batch.drop_column("state")
        batch.drop_column("scope")
