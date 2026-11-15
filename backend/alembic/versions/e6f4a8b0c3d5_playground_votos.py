"""playground: voto por página («Mejor»)

Revision ID: e6f4a8b0c3d5
Revises: d5e3f7a9b2c4
"""
import sqlalchemy as sa
from alembic import op

revision = 'e6f4a8b0c3d5'
down_revision = 'd5e3f7a9b2c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("playground_runs") as batch:
        batch.add_column(sa.Column("votes", sa.JSON()))


def downgrade() -> None:
    with op.batch_alter_table("playground_runs") as batch:
        batch.drop_column("votes")
