"""segmentos: marca de traducción editada a mano

Revision ID: b3c1d2e4f5a6
Revises: a7a5ed90322a
Create Date: 2026-11-11 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c1d2e4f5a6'
down_revision = 'a7a5ed90322a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('segments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('edited', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('segments', schema=None) as batch_op:
        batch_op.drop_column('edited')
