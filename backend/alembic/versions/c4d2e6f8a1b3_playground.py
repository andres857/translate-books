"""playground: borradores de prompt y ejecuciones de evaluación

Revision ID: c4d2e6f8a1b3
Revises: b3c1d2e4f5a6
"""
import sqlalchemy as sa
from alembic import op

revision = 'c4d2e6f8a1b3'
down_revision = 'b3c1d2e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "playground_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("task", sa.String(16), nullable=False),
        sa.Column("pages", sa.String(32), nullable=False),
        sa.Column("chapter", sa.Text()),
        sa.Column("variants", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("current_variant", sa.Integer()),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_playground_runs_job_id", "playground_runs", ["job_id"])
    op.create_index("ix_playground_runs_status", "playground_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_playground_runs_status", "playground_runs")
    op.drop_index("ix_playground_runs_job_id", "playground_runs")
    op.drop_table("playground_runs")
    op.drop_table("prompt_drafts")
