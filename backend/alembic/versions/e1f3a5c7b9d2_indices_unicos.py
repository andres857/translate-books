"""índices únicos: (page_id, seg_key) en bloques y un término por libro (o global) en glosario y términos

Revision ID: e1f3a5c7b9d2
Revises: d2e4f6a8c0b1
"""
from alembic import op

revision = 'e1f3a5c7b9d2'
down_revision = 'd2e4f6a8c0b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # índices (no constraints): SQLite los crea sin reconstruir las tablas. document_id NULL (global) cuenta como 0.
    op.execute("CREATE UNIQUE INDEX uq_segments_page_seg_key ON segments (page_id, seg_key)")
    op.execute("CREATE UNIQUE INDEX uq_glossary_doc_source ON glossary (coalesce(document_id, 0), lower(source))")
    op.execute("CREATE UNIQUE INDEX uq_protected_terms_doc_term ON protected_terms (coalesce(document_id, 0), term)")


def downgrade() -> None:
    op.execute("DROP INDEX uq_protected_terms_doc_term")
    op.execute("DROP INDEX uq_glossary_doc_source")
    op.execute("DROP INDEX uq_segments_page_seg_key")
