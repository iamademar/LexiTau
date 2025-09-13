"""enable_pgvector_extension

Revision ID: a156654a529b
Revises: b7e27794d4c6
Create Date: 2025-09-07 01:27:41.039723

"""
from alembic import op
import sqlalchemy as sa


revision = 'a156654a529b'
down_revision = 'b7e27794d4c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Disable pgvector extension (optional - be careful with this)
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE")