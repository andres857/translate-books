"""archivos en almacenamiento S3 (solo la key)

Revision ID: f7a5b9c1d4e6
Revises: e6f4a8b0c3d5
"""
import sqlalchemy as sa
from alembic import op

revision = 'f7a5b9c1d4e6'
down_revision = 'e6f4a8b0c3d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(512), nullable=False, unique=True),
        sa.Column("original_name", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("private", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("files")
