"""Add business_id to child tables and sync trigger from documents

Revision ID: b935ef8c415b
Revises: b7e27794d4c6
Create Date: 2025-09-13 12:27:59.509921

"""
from alembic import op
import sqlalchemy as sa

revision = 'b935ef8c415b'
down_revision = 'b7e27794d4c6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1) Add nullable columns
    op.add_column("extracted_fields", sa.Column("business_id", sa.Integer(), nullable=True))
    op.add_column("line_items", sa.Column("business_id", sa.Integer(), nullable=True))
    op.add_column("field_corrections", sa.Column("business_id", sa.Integer(), nullable=True))

    # 2) Backfill from documents
    op.execute("""
        UPDATE extracted_fields ef
        SET business_id = d.business_id
        FROM documents d
        WHERE ef.document_id = d.id;
    """)
    op.execute("""
        UPDATE line_items li
        SET business_id = d.business_id
        FROM documents d
        WHERE li.document_id = d.id;
    """)
    op.execute("""
        UPDATE field_corrections fc
        SET business_id = d.business_id
        FROM documents d
        WHERE fc.document_id = d.id;
    """)

    # 3) NOT NULL
    op.alter_column("extracted_fields", "business_id", nullable=False)
    op.alter_column("line_items", "business_id", nullable=False)
    op.alter_column("field_corrections", "business_id", nullable=False)

    # 4) FKs → businesses(id)
    op.create_foreign_key(
        "extracted_fields_business_fk", "extracted_fields", "businesses",
        ["business_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "line_items_business_fk", "line_items", "businesses",
        ["business_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "field_corrections_business_fk", "field_corrections", "businesses",
        ["business_id"], ["id"], ondelete="RESTRICT"
    )

    # 5) Indexes
    op.create_index("ix_extracted_fields_business_id", "extracted_fields", ["business_id"])
    op.create_index("ix_line_items_business_id", "line_items", ["business_id"])
    op.create_index("ix_field_corrections_business_id", "field_corrections", ["business_id"])
    op.create_index("ix_extracted_fields_doc_biz", "extracted_fields", ["document_id", "business_id"])
    op.create_index("ix_line_items_doc_biz", "line_items", ["document_id", "business_id"])
    op.create_index("ix_field_corrections_doc_biz", "field_corrections", ["document_id", "business_id"])

    # 6) Trigger function to enforce/auto-sync from documents
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_business_id_from_document()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
      doc_biz integer;
    BEGIN
      SELECT business_id INTO doc_biz FROM documents WHERE id = NEW.document_id;
      IF doc_biz IS NULL THEN
        RAISE EXCEPTION 'Document % not found for %', NEW.document_id, TG_TABLE_NAME;
      END IF;

      IF NEW.business_id IS NULL THEN
        NEW.business_id := doc_biz;
      ELSIF NEW.business_id <> doc_biz THEN
        RAISE EXCEPTION 'business_id mismatch on %: got %, expected % from documents',
          TG_TABLE_NAME, NEW.business_id, doc_biz;
      END IF;

      RETURN NEW;
    END
    $$;
    """)

    # 7) Attach BEFORE triggers
    for tbl in ("extracted_fields", "line_items", "field_corrections"):
        op.execute(f"""
        DROP TRIGGER IF EXISTS {tbl}_biz_sync ON {tbl};
        CREATE TRIGGER {tbl}_biz_sync
        BEFORE INSERT OR UPDATE OF document_id, business_id
        ON {tbl}
        FOR EACH ROW
        EXECUTE FUNCTION enforce_business_id_from_document();
        """)

def downgrade() -> None:
    # Remove triggers
    for tbl in ("extracted_fields", "line_items", "field_corrections"):
        op.execute(f"DROP TRIGGER IF EXISTS {tbl}_biz_sync ON {tbl};")
    op.execute("DROP FUNCTION IF EXISTS enforce_business_id_from_document();")

    # Drop indexes
    op.drop_index("ix_field_corrections_doc_biz", table_name="field_corrections")
    op.drop_index("ix_line_items_doc_biz", table_name="line_items")
    op.drop_index("ix_extracted_fields_doc_biz", table_name="extracted_fields")
    op.drop_index("ix_field_corrections_business_id", table_name="field_corrections")
    op.drop_index("ix_line_items_business_id", table_name="line_items")
    op.drop_index("ix_extracted_fields_business_id", table_name="extracted_fields")

    # Drop FKs
    op.drop_constraint("field_corrections_business_fk", "field_corrections", type_="foreignkey")
    op.drop_constraint("line_items_business_fk", "line_items", type_="foreignkey")
    op.drop_constraint("extracted_fields_business_fk", "extracted_fields", type_="foreignkey")

    # Allow NULLs and drop columns
    op.alter_column("field_corrections", "business_id", nullable=True)
    op.alter_column("line_items", "business_id", nullable=True)
    op.alter_column("extracted_fields", "business_id", nullable=True)

    op.drop_column("field_corrections", "business_id")
    op.drop_column("line_items", "business_id")
    op.drop_column("extracted_fields", "business_id")