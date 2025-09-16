"""add business_id to extracted_fields, line_items, field_corrections

Revision ID: 84b12b56b29c
Revises: 90a76db1c2da
Create Date: 2025-09-16 21:02:04.157634

"""
from alembic import op
import sqlalchemy as sa


revision = '84b12b56b29c'
down_revision = '90a76db1c2da'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add nullable business_id columns
    op.add_column('extracted_fields', sa.Column('business_id', sa.Integer(), nullable=True))
    op.add_column('line_items', sa.Column('business_id', sa.Integer(), nullable=True))
    op.add_column('field_corrections', sa.Column('business_id', sa.Integer(), nullable=True))

    # Step 2: Backfill business_id from documents table
    op.execute("""
        UPDATE extracted_fields
        SET business_id = documents.business_id
        FROM documents
        WHERE extracted_fields.document_id = documents.id
    """)

    op.execute("""
        UPDATE line_items
        SET business_id = documents.business_id
        FROM documents
        WHERE line_items.document_id = documents.id
    """)

    op.execute("""
        UPDATE field_corrections
        SET business_id = documents.business_id
        FROM documents
        WHERE field_corrections.document_id = documents.id
    """)

    # Step 3: Make columns NOT NULL
    op.alter_column('extracted_fields', 'business_id', nullable=False)
    op.alter_column('line_items', 'business_id', nullable=False)
    op.alter_column('field_corrections', 'business_id', nullable=False)

    # Step 4: Add foreign key constraints
    op.create_foreign_key('fk_extracted_fields_business_id', 'extracted_fields', 'businesses', ['business_id'], ['id'])
    op.create_foreign_key('fk_line_items_business_id', 'line_items', 'businesses', ['business_id'], ['id'])
    op.create_foreign_key('fk_field_corrections_business_id', 'field_corrections', 'businesses', ['business_id'], ['id'])

    # Step 5: Add single column indexes
    op.create_index(op.f('ix_extracted_fields_business_id'), 'extracted_fields', ['business_id'], unique=False)
    op.create_index(op.f('ix_line_items_business_id'), 'line_items', ['business_id'], unique=False)
    op.create_index(op.f('ix_field_corrections_business_id'), 'field_corrections', ['business_id'], unique=False)

    # Step 6: Add composite indexes for tenant-scoped queries
    op.create_index('ix_extracted_fields_business_document', 'extracted_fields', ['business_id', 'document_id'], unique=False)
    op.create_index('ix_line_items_business_document', 'line_items', ['business_id', 'document_id'], unique=False)
    op.create_index('ix_field_corrections_business_document', 'field_corrections', ['business_id', 'document_id'], unique=False)


def downgrade() -> None:
    # Drop composite indexes
    op.drop_index('ix_field_corrections_business_document', table_name='field_corrections')
    op.drop_index('ix_line_items_business_document', table_name='line_items')
    op.drop_index('ix_extracted_fields_business_document', table_name='extracted_fields')

    # Drop single column indexes
    op.drop_index(op.f('ix_field_corrections_business_id'), table_name='field_corrections')
    op.drop_index(op.f('ix_line_items_business_id'), table_name='line_items')
    op.drop_index(op.f('ix_extracted_fields_business_id'), table_name='extracted_fields')

    # Drop foreign key constraints
    op.drop_constraint('fk_field_corrections_business_id', 'field_corrections', type_='foreignkey')
    op.drop_constraint('fk_line_items_business_id', 'line_items', type_='foreignkey')
    op.drop_constraint('fk_extracted_fields_business_id', 'extracted_fields', type_='foreignkey')

    # Drop columns
    op.drop_column('field_corrections', 'business_id')
    op.drop_column('line_items', 'business_id')
    op.drop_column('extracted_fields', 'business_id')