"""
Test JSONB compatibility type works correctly.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.column_profile import ColumnProfile


def test_column_profile_jsonb_fields_sqlite(db_session):
    """Test that JSONB fields work correctly with SQLite (unit test DB)"""

    # Create a ColumnProfile with JSONB data
    profile = ColumnProfile(
        database_name="test_db",
        table_name="test_table",
        column_name="test_column",
        data_type="VARCHAR",
        table_row_count=1000,
        null_count=50,
        non_null_count=950,
        distinct_count=Decimal("800.0"),

        # Test JSONB fields
        char_classes={
            "digits_only": 123,
            "alpha_only": 456,
            "has_punct": 78,
            "has_space": 90,
            "mixed": 203,
            "total": 950
        },
        common_prefixes=[
            {"prefix": "usr", "count": 45},
            {"prefix": "sys", "count": 23}
        ],
        top_k_values=[
            {"value": "user123", "count": 87},
            {"value": "admin", "count": 23}
        ],
        distinct_sample=["value1", "value2", "value3"],
        minhash_signature=[12345, 67890, 11111],

        # Required text fields
        english_description="Test description",
        short_summary="Test summary",
        long_summary="Long summary",

        # Required timestamp
        generated_at=datetime.now(timezone.utc)
    )

    # Save to database
    db_session.add(profile)
    db_session.commit()

    # Retrieve and verify data integrity
    retrieved = db_session.query(ColumnProfile).filter_by(
        database_name="test_db",
        table_name="test_table",
        column_name="test_column"
    ).first()

    assert retrieved is not None

    # Test char_classes JSONB field
    assert retrieved.char_classes["digits_only"] == 123
    assert retrieved.char_classes["total"] == 950

    # Test common_prefixes JSONB field
    assert len(retrieved.common_prefixes) == 2
    assert retrieved.common_prefixes[0]["prefix"] == "usr"
    assert retrieved.common_prefixes[0]["count"] == 45

    # Test top_k_values JSONB field
    assert len(retrieved.top_k_values) == 2
    assert retrieved.top_k_values[0]["value"] == "user123"
    assert retrieved.top_k_values[0]["count"] == 87

    # Test distinct_sample JSONB field (list of strings)
    assert "value1" in retrieved.distinct_sample
    assert len(retrieved.distinct_sample) == 3

    # Test minhash_signature JSONB field (list of ints)
    assert retrieved.minhash_signature[0] == 12345
    assert len(retrieved.minhash_signature) == 3


def test_column_profile_jsonb_updates(db_session):
    """Test updating JSONB fields"""

    # Create initial record
    profile = ColumnProfile(
        database_name="test_db_update",
        table_name="test_table",
        column_name="test_column",
        data_type="VARCHAR",
        table_row_count=100,
        null_count=0,
        non_null_count=100,
        distinct_count=Decimal("90.0"),

        char_classes={"total": 100},
        common_prefixes=[],
        top_k_values=[],
        distinct_sample=[],
        minhash_signature=[],

        english_description="Test",
        short_summary="Test",
        long_summary="Test",
        generated_at=datetime.now(timezone.utc)
    )

    db_session.add(profile)
    db_session.commit()

    # Update JSONB fields - need to reassign for SQLAlchemy to detect changes
    updated_char_classes = profile.char_classes.copy()
    updated_char_classes["new_field"] = 999
    profile.char_classes = updated_char_classes

    profile.common_prefixes = [{"prefix": "new", "count": 10}]
    profile.top_k_values = [{"value": "updated", "count": 50}]
    profile.distinct_sample = ["new_value"]
    profile.minhash_signature = [99999]

    db_session.commit()

    # Verify updates
    updated = db_session.query(ColumnProfile).filter_by(
        database_name="test_db_update"
    ).first()

    assert updated.char_classes["new_field"] == 999
    assert updated.common_prefixes[0]["prefix"] == "new"
    assert updated.top_k_values[0]["value"] == "updated"
    assert updated.distinct_sample[0] == "new_value"
    assert updated.minhash_signature[0] == 99999


def test_column_profile_null_jsonb_fields(db_session):
    """Test that JSONB fields can be None"""

    profile = ColumnProfile(
        database_name="test_db_null",
        table_name="test_table",
        column_name="test_column",
        data_type="VARCHAR",
        table_row_count=0,
        null_count=0,
        non_null_count=0,
        distinct_count=None,

        # All JSONB fields as None
        char_classes=None,
        common_prefixes=None,
        top_k_values=None,
        distinct_sample=None,
        minhash_signature=None,

        english_description="Test",
        short_summary="Test",
        long_summary="Test",
        generated_at=datetime.now(timezone.utc)
    )

    db_session.add(profile)
    db_session.commit()

    # Verify None values are preserved
    retrieved = db_session.query(ColumnProfile).filter_by(
        database_name="test_db_null"
    ).first()

    assert retrieved.char_classes is None
    assert retrieved.common_prefixes is None
    assert retrieved.top_k_values is None
    assert retrieved.distinct_sample is None
    assert retrieved.minhash_signature is None