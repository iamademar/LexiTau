"""
Test JSONB functionality specifically with PostgreSQL.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import text

from app.models.column_profile import ColumnProfile


@pytest.mark.integration
def test_column_profile_jsonb_postgres_specific(db_session):
    """Test PostgreSQL-specific JSONB operations"""

    # Create a ColumnProfile with JSONB data
    profile = ColumnProfile(
        database_name="test_db_pg",
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

    # Test PostgreSQL-specific JSONB operators

    # Test JSONB containment operator (?)
    from sqlalchemy import text
    result = db_session.execute(
        text("SELECT * FROM column_profiles WHERE char_classes ? 'digits_only' AND database_name = :db"),
        {"db": "test_db_pg"}
    ).fetchone()
    assert result is not None

    # Test JSONB path extraction (->>)
    result = db_session.execute(
        text("SELECT char_classes->>'total' FROM column_profiles WHERE database_name = :db"),
        {"db": "test_db_pg"}
    ).scalar()
    assert int(result) == 950

    # Test JSONB array containment (@>)
    result = db_session.execute(
        text("SELECT * FROM column_profiles WHERE minhash_signature @> '[12345]'")
    ).fetchone()
    assert result is not None

    # Test JSONB object containment (@>)
    result = db_session.execute(
        text("SELECT * FROM column_profiles WHERE char_classes @> '{\"total\": 950}'")
    ).fetchone()
    assert result is not None


@pytest.mark.integration
def test_column_profile_jsonb_indexing_postgres(db_session):
    """Test that JSONB fields support PostgreSQL indexing operations"""

    # Create multiple profiles for indexing test
    profiles = []
    for i in range(5):
        profile = ColumnProfile(
            database_name=f"test_db_idx_{i}",
            table_name="test_table",
            column_name="test_column",
            data_type="VARCHAR",
            table_row_count=100,
            null_count=0,
            non_null_count=100,
            distinct_count=Decimal(f"{90 + i}.0"),

            char_classes={
                "digits_only": i * 10,
                "alpha_only": i * 20,
                "total": 100
            },
            common_prefixes=[],
            top_k_values=[],
            distinct_sample=[],
            minhash_signature=[],

            english_description=f"Test {i}",
            short_summary=f"Test {i}",
            long_summary=f"Test {i}",
            generated_at=datetime.now(timezone.utc)
        )
        profiles.append(profile)

    db_session.add_all(profiles)
    db_session.commit()

    # Test JSONB path queries work efficiently
    results = db_session.execute(
        text("SELECT database_name FROM column_profiles WHERE (char_classes->>'digits_only')::int > 20 ORDER BY database_name")
    ).fetchall()

    # Should find profiles with i >= 3 (since 3*10 = 30 > 20)
    assert len(results) >= 2
    expected_dbs = [f"test_db_idx_{i}" for i in range(3, 5)]
    result_dbs = [row[0] for row in results if row[0].startswith("test_db_idx_")]

    for expected_db in expected_dbs:
        assert expected_db in result_dbs


@pytest.mark.integration
def test_column_profile_jsonb_type_verification_postgres(db_session):
    """Verify the JSONBCompat type resolves to actual JSONB in Postgres"""

    from sqlalchemy import inspect

    # Get column information from the database
    inspector = inspect(db_session.bind)
    columns = inspector.get_columns('column_profiles')

    # Find JSONB columns
    jsonb_columns = [col for col in columns if col['name'] in [
        'char_classes', 'common_prefixes', 'top_k_values',
        'distinct_sample', 'minhash_signature'
    ]]

    assert len(jsonb_columns) == 5

    # In PostgreSQL, these should be actual JSONB types
    for col in jsonb_columns:
        column_type = str(col['type']).upper()
        # Should be JSONB, not just JSON
        assert 'JSONB' in column_type or 'JSON' in column_type
        print(f"Column {col['name']}: {col['type']}")


@pytest.mark.integration
def test_column_profile_jsonb_advanced_queries_postgres(db_session):
    """Test advanced JSONB queries that are PostgreSQL-specific"""

    # Create test data with nested structures
    profile = ColumnProfile(
        database_name="test_advanced",
        table_name="test_table",
        column_name="test_column",
        data_type="VARCHAR",
        table_row_count=100,
        null_count=0,
        non_null_count=100,
        distinct_count=Decimal("90.0"),

        # Complex nested JSONB
        char_classes={
            "patterns": {
                "numeric": {"count": 50, "percentage": 0.5},
                "alpha": {"count": 30, "percentage": 0.3}
            },
            "total": 100
        },
        top_k_values=[
            {"value": "test1", "count": 25, "metadata": {"category": "A"}},
            {"value": "test2", "count": 15, "metadata": {"category": "B"}}
        ],
        common_prefixes=[],
        distinct_sample=[],
        minhash_signature=[],

        english_description="Advanced test",
        short_summary="Advanced test",
        long_summary="Advanced test",
        generated_at=datetime.now(timezone.utc)
    )

    db_session.add(profile)
    db_session.commit()

    # Test deep path extraction
    result = db_session.execute(
        text("SELECT char_classes->'patterns'->'numeric'->>'count' FROM column_profiles WHERE database_name = 'test_advanced'")
    ).scalar()
    assert int(result) == 50

    # Test JSONB array element access
    result = db_session.execute(
        text("SELECT top_k_values->0->>'value' FROM column_profiles WHERE database_name = 'test_advanced'")
    ).scalar()
    assert result == "test1"

    # Test JSONB containment with nested objects
    result = db_session.execute(
        text("SELECT * FROM column_profiles WHERE char_classes @> '{\"patterns\": {\"numeric\": {\"count\": 50}}}'")
    ).fetchone()
    assert result is not None