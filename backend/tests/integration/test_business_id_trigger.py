import pytest
from sqlalchemy import text
from app.test_db import TestingSessionLocal


@pytest.mark.integration
def test_trigger_auto_populates_business_id():
    """Test that the trigger auto-populates business_id from documents when not provided"""
    db = TestingSessionLocal()
    try:
        # Create a business
        business_result = db.execute(text("""
            INSERT INTO businesses(name, created_at)
            VALUES ('Test Business', NOW())
            RETURNING id
        """))
        business_id = business_result.scalar_one()

        # Create a document with this business_id
        document_result = db.execute(text("""
            INSERT INTO documents(business_id, filename, file_size, file_type, status, created_at)
            VALUES (:business_id, 'test.pdf', 1024, 'pdf', 'uploaded', NOW())
            RETURNING id
        """), {"business_id": business_id})
        document_id = document_result.scalar_one()

        # Insert extracted_field without business_id - trigger should auto-populate it
        db.execute(text("""
            INSERT INTO extracted_fields(document_id, field_name, value)
            VALUES (:document_id, 'test_field', 'test_value')
        """), {"document_id": document_id})

        # Check that business_id was auto-populated
        result = db.execute(text("""
            SELECT business_id FROM extracted_fields
            WHERE document_id = :document_id AND field_name = 'test_field'
        """), {"document_id": document_id})
        auto_populated_business_id = result.scalar_one()

        assert auto_populated_business_id == business_id

        db.commit()
    finally:
        db.close()


@pytest.mark.integration
def test_trigger_rejects_mismatched_business_id():
    """Test that the trigger rejects inserts with mismatched business_id"""
    db = TestingSessionLocal()
    try:
        # Create two businesses
        business1_result = db.execute(text("""
            INSERT INTO businesses(name, created_at)
            VALUES ('Business 1', NOW())
            RETURNING id
        """))
        business1_id = business1_result.scalar_one()

        business2_result = db.execute(text("""
            INSERT INTO businesses(name, created_at)
            VALUES ('Business 2', NOW())
            RETURNING id
        """))
        business2_id = business2_result.scalar_one()

        # Create a document with business1_id
        document_result = db.execute(text("""
            INSERT INTO documents(business_id, filename, file_size, file_type, status, created_at)
            VALUES (:business_id, 'test.pdf', 1024, 'pdf', 'uploaded', NOW())
            RETURNING id
        """), {"business_id": business1_id})
        document_id = document_result.scalar_one()

        # Try to insert line_item with wrong business_id - should fail
        with pytest.raises(Exception) as exc_info:
            db.execute(text("""
                INSERT INTO line_items(document_id, business_id, description, quantity, unit_price, total)
                VALUES (:document_id, :business_id, 'Test Item', 1.0, 10.00, 10.00)
            """), {"document_id": document_id, "business_id": business2_id})
            db.commit()

        # Check that the error message mentions business_id mismatch
        assert "business_id mismatch" in str(exc_info.value)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.mark.integration
def test_trigger_works_for_all_child_tables():
    """Test that the trigger works for all three child tables"""
    db = TestingSessionLocal()
    try:
        # Create a business and document
        business_result = db.execute(text("""
            INSERT INTO businesses(name, created_at)
            VALUES ('Test Business', NOW())
            RETURNING id
        """))
        business_id = business_result.scalar_one()

        document_result = db.execute(text("""
            INSERT INTO documents(business_id, filename, file_size, file_type, status, created_at)
            VALUES (:business_id, 'test.pdf', 1024, 'pdf', 'uploaded', NOW())
            RETURNING id
        """), {"business_id": business_id})
        document_id = document_result.scalar_one()

        # Create a user for field_corrections
        user_result = db.execute(text("""
            INSERT INTO users(business_id, email, hashed_password, is_active, created_at)
            VALUES (:business_id, 'test@example.com', 'hashed_pw', true, NOW())
            RETURNING id
        """), {"business_id": business_id})
        user_id = user_result.scalar_one()

        # Test extracted_fields
        db.execute(text("""
            INSERT INTO extracted_fields(document_id, field_name, value)
            VALUES (:document_id, 'invoice_date', '2023-01-01')
        """), {"document_id": document_id})

        # Test line_items
        db.execute(text("""
            INSERT INTO line_items(document_id, description, quantity, unit_price, total)
            VALUES (:document_id, 'Test Service', 2.0, 50.00, 100.00)
        """), {"document_id": document_id})

        # Test field_corrections
        db.execute(text("""
            INSERT INTO field_corrections(document_id, field_name, original_value, corrected_value, corrected_by)
            VALUES (:document_id, 'invoice_date', '2023-01-01', '2023-01-02', :user_id)
        """), {"document_id": document_id, "user_id": user_id})

        # Verify all have correct business_id
        extracted_field_business_id = db.execute(text("""
            SELECT business_id FROM extracted_fields WHERE document_id = :document_id
        """), {"document_id": document_id}).scalar_one()

        line_item_business_id = db.execute(text("""
            SELECT business_id FROM line_items WHERE document_id = :document_id
        """), {"document_id": document_id}).scalar_one()

        field_correction_business_id = db.execute(text("""
            SELECT business_id FROM field_corrections WHERE document_id = :document_id
        """), {"document_id": document_id}).scalar_one()

        assert extracted_field_business_id == business_id
        assert line_item_business_id == business_id
        assert field_correction_business_id == business_id

        db.commit()
    finally:
        db.close()


@pytest.mark.integration
def test_trigger_handles_document_update():
    """Test that the trigger prevents updating document_id to different business"""
    db = TestingSessionLocal()
    try:
        # Create two businesses
        business1_result = db.execute(text("""
            INSERT INTO businesses(name, created_at)
            VALUES ('Business 1', NOW())
            RETURNING id
        """))
        business1_id = business1_result.scalar_one()

        business2_result = db.execute(text("""
            INSERT INTO businesses(name, created_at)
            VALUES ('Business 2', NOW())
            RETURNING id
        """))
        business2_id = business2_result.scalar_one()

        # Create documents for both businesses
        document1_result = db.execute(text("""
            INSERT INTO documents(business_id, filename, file_size, file_type, status, created_at)
            VALUES (:business_id, 'doc1.pdf', 1024, 'pdf', 'uploaded', NOW())
            RETURNING id
        """), {"business_id": business1_id})
        document1_id = document1_result.scalar_one()

        document2_result = db.execute(text("""
            INSERT INTO documents(business_id, filename, file_size, file_type, status, created_at)
            VALUES (:business_id, 'doc2.pdf', 1024, 'pdf', 'uploaded', NOW())
            RETURNING id
        """), {"business_id": business2_id})
        document2_id = document2_result.scalar_one()

        # Create extracted_field for document1
        db.execute(text("""
            INSERT INTO extracted_fields(document_id, field_name, value)
            VALUES (:document_id, 'test_field', 'test_value')
        """), {"document_id": document1_id})

        # Try to update document_id to document2 (different business) - should fail
        with pytest.raises(Exception) as exc_info:
            db.execute(text("""
                UPDATE extracted_fields
                SET document_id = :new_document_id
                WHERE document_id = :old_document_id
            """), {"new_document_id": document2_id, "old_document_id": document1_id})
            db.commit()

        # Check that the error mentions business_id mismatch
        assert "business_id mismatch" in str(exc_info.value)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()