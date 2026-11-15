"""historial del playground: intentos (evaluaciones y pruebas de página)

Revision ID: a8b6c0d2e5f7
Revises: f7a5b9c1d4e6
"""
import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = 'a8b6c0d2e5f7'
down_revision = 'f7a5b9c1d4e6'
branch_labels = None
depends_on = None

CFG = ("provider", "model", "thinking", "prompt", "prompt_name", "prompt_text")
# tarifa punta (USD por millón) sin datos de caché: estimado por arriba para evaluaciones anteriores
PRICES = {"deepseek-flash": (0.30, 1.20), "deepseek-v4-pro": (1.32, 3.96)}
ALIASES = {"deepseek-pro": "deepseek-v4-pro", "deepseek-v4-flash": "deepseek-flash"}


def _when(value):
    """SQLite devuelve la fecha como texto en una consulta cruda; la tabla necesita un datetime."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now(timezone.utc)


def _cost(v: dict, r: dict):
    if v.get("provider") == "fake":
        return 0.0
    price = PRICES.get(ALIASES.get(v.get("model"), v.get("model")))
    if price is None:
        return r.get("cost_usd")
    return ((r.get("tokens_in") or 0) * price[0] + (r.get("tokens_out") or 0) * price[1]) / 1e6


def upgrade() -> None:
    attempts = op.create_table(
        "playground_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("playground_runs.id"), nullable=False, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("label", sa.String(4), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("pages", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_cache_hit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("pdf", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # evaluaciones anteriores: un intento por variante con lo que quedó guardado (sin copia propia del PDF)
    conn = op.get_bind()
    runs = conn.execute(sa.text("SELECT id, job_id, pages, variants, results, updated_at FROM playground_runs")).fetchall()
    rows = []
    for run_id, job_id, pages, variants, results, updated in runs:
        variants = json.loads(variants) if isinstance(variants, str) else variants or []
        results = json.loads(results) if isinstance(results, str) else results or []
        for v, r in zip(variants, results):
            rows.append({
                "run_id": run_id, "job_id": job_id, "label": v.get("label", "?"), "kind": "run", "pages": pages or "",
                "config": {k: v.get(k) for k in CFG}, "segments": r.get("segments") or {},
                "seconds": r.get("seconds") or 0, "calls": r.get("calls") or 0, "tokens_in": r.get("tokens_in") or 0,
                "tokens_out": r.get("tokens_out") or 0, "tokens_cache_hit": 0,
                "cost_usd": _cost(v, r),
                "error": r.get("error"), "pdf": None, "created_at": _when(updated),
            })
    if rows:
        op.bulk_insert(attempts, rows)


def downgrade() -> None:
    op.drop_table("playground_attempts")
