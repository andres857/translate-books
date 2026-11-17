"""login: usuarios, sesiones, límites de intentos, eventos de seguridad y dueño de cada trabajo

Revision ID: d2e4f6a8c0b1
Revises: c1d3e5f7a9b2
"""
import sqlalchemy as sa
from alembic import op

revision = 'd2e4f6a8c0b1'
down_revision = 'c1d3e5f7a9b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("temp_password_expires_at", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reauth_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(256)),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "auth_rate_limits",
        sa.Column("bucket", sa.String(96), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "auth_security_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(48), nullable=False),
        sa.Column("user_id", sa.Integer()),
        sa.Column("actor_id", sa.Integer()),
        sa.Column("ip", sa.String(64)),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_security_events_type", "auth_security_events", ["type"])
    op.create_index("ix_auth_security_events_user_id", "auth_security_events", ["user_id"])
    # ADD COLUMN simple (sin recrear la tabla: con foreign_keys=ON SQLite no deja borrar `jobs`)
    # (Alembic no admite FK en add_column de SQLite: SQL directo, válido porque la columna admite NULL)
    op.execute("ALTER TABLE jobs ADD COLUMN owner_id INTEGER REFERENCES users (id)")
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_owner_id", "jobs")
    op.drop_column("jobs", "owner_id")  # SQLite ≥ 3.35
    op.drop_table("auth_security_events")
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_auth_sessions_user_id", "auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
