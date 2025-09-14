"""Integration tests for SELECT * column exclusion functionality."""
import pytest
from sqlalchemy import text

from app.services.vanna_service import guard_and_rewrite_sql


@pytest.mark.integration
def test_exclude_bytea_columns(test_engine):
    """Test that bytea columns are excluded from SELECT * expansion."""
    # First, add a bytea column to the documents table for testing
    with test_engine.begin() as conn:
        # Add bytea column if it doesn't exist
        conn.execute(text("""
            ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS binary_data bytea
        """))

    sql = "SELECT * FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Should expand * but exclude bytea column
    assert "SELECT *" not in final_sql
    assert "star_expanded" in guard_flags

    # Should not contain bytea column
    assert "binary_data" not in final_sql

    # Should contain normal columns
    assert "documents_id" in final_sql
    assert "documents_filename" in final_sql

    # Check metadata for exclusion info
    assert "star" in metadata
    assert metadata["star"]["star_expanded"] is True
    assert "excluded" in metadata["star"]

    # Should have exclusions recorded for documents table
    docs_exclusions = metadata["star"]["excluded"].get("public.documents", {})
    assert "binary_data" in docs_exclusions.get("excluded_by_type", [])


@pytest.mark.integration
def test_exclude_password_columns(test_engine):
    """Test that columns matching sensitive name patterns are excluded."""
    # Add password-related columns to documents table for testing (since users table is not allowed)
    with test_engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS secret_key text,
            ADD COLUMN IF NOT EXISTS api_token text,
            ADD COLUMN IF NOT EXISTS password_reset_token text
        """))

    sql = "SELECT * FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Should expand * but exclude sensitive columns
    assert "SELECT *" not in final_sql
    assert "star_expanded" in guard_flags

    # Should not contain sensitive columns
    assert "secret_key" not in final_sql
    assert "api_token" not in final_sql
    assert "password_reset_token" not in final_sql

    # Should contain normal columns
    assert "documents_id" in final_sql
    assert "documents_filename" in final_sql

    # Check metadata for exclusion info
    assert "star" in metadata
    docs_exclusions = metadata["star"]["excluded"].get("public.documents", {})

    # Should have name pattern exclusions
    name_pattern_exclusions = docs_exclusions.get("excluded_by_name_pattern", [])
    assert "secret_key" in name_pattern_exclusions
    assert "api_token" in name_pattern_exclusions
    assert "password_reset_token" in name_pattern_exclusions


@pytest.mark.integration
def test_explicit_column_exclusions(test_engine):
    """Test that per-table explicit exclusions work correctly."""
    sql = "SELECT * FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Should expand * but exclude explicitly configured columns
    assert "SELECT *" not in final_sql
    assert "star_expanded" in guard_flags

    # Should not contain explicitly excluded columns (from settings)
    assert "file_url" not in final_sql  # Configured in VANNA_EXPAND_EXCLUDE_COLUMNS

    # Should contain non-excluded columns
    assert "documents_id" in final_sql
    assert "documents_filename" in final_sql

    # Check metadata for exclusion info
    assert "star" in metadata
    docs_exclusions = metadata["star"]["excluded"].get("public.documents", {})

    # Should have explicit exclusions recorded
    explicit_exclusions = docs_exclusions.get("excluded_by_explicit", [])
    assert "file_url" in explicit_exclusions


@pytest.mark.integration
def test_explicit_column_selection_bypasses_exclusions(test_engine):
    """Test that explicit column selection bypasses exclusion guards."""
    # Test selecting explicitly excluded columns - should work
    sql = """
    SELECT d.file_url, d.filename, c.name
    FROM public.documents d
    JOIN public.clients c ON d.client_id = c.id
    WHERE business_id = :business_id
      AND d.business_id = :business_id
      AND c.business_id = :business_id
    """
    business_id = 1

    # This should NOT raise any GuardError even though we're selecting excluded columns
    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Should keep explicit columns unchanged
    assert "d.file_url" in final_sql
    assert "d.filename" in final_sql
    assert "c.name" in final_sql

    # Should not have star expansion
    assert "star_expanded" not in guard_flags
    assert metadata["star"]["star_expanded"] is False

    # Should not have SELECT * anywhere
    assert "SELECT *" not in final_sql


@pytest.mark.integration
def test_mixed_star_and_explicit_with_exclusions(test_engine):
    """Test SELECT * expansion with explicit columns, respecting exclusions."""
    sql = """
    SELECT *, d.file_url as document_url
    FROM public.documents d
    WHERE business_id = :business_id AND d.business_id = :business_id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Should expand * but keep explicit column
    assert "SELECT *" not in final_sql
    assert "star_expanded" in guard_flags
    assert "document_url" in final_sql

    # Should not contain file_url from * expansion (excluded)
    # But should contain it from explicit selection
    file_url_count = final_sql.count("file_url")
    assert file_url_count == 1  # Only from explicit "d.file_url as document_url"

    # Should contain other expanded columns
    assert "d_id" in final_sql
    assert "d_filename" in final_sql

    # Check exclusions were recorded
    docs_exclusions = metadata["star"]["excluded"].get("public.documents", {})
    assert "file_url" in docs_exclusions.get("excluded_by_explicit", [])


@pytest.mark.integration
def test_multiple_table_exclusions(test_engine):
    """Test exclusions work correctly across multiple tables in JOINs."""
    sql = """
    SELECT *
    FROM public.documents d
    JOIN public.clients c ON d.client_id = c.id
    WHERE business_id = :business_id
      AND d.business_id = :business_id
      AND c.business_id = :business_id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Should expand * from both tables
    assert "SELECT *" not in final_sql
    assert "star_expanded" in guard_flags

    # Should not contain excluded columns from documents table
    assert "file_url" not in final_sql  # Excluded from documents

    # Should contain non-excluded columns from both tables
    assert "d_id" in final_sql
    assert "d_filename" in final_sql
    assert "c_id" in final_sql
    assert "c_name" in final_sql

    # Check metadata has exclusions for documents table
    star_exclusions = metadata["star"]["excluded"]
    assert "public.documents" in star_exclusions

    # Verify documents table exclusions
    docs_exclusions = star_exclusions["public.documents"]
    assert "file_url" in docs_exclusions.get("excluded_by_explicit", [])


@pytest.mark.integration
def test_no_exclusions_when_no_star(test_engine):
    """Test that metadata doesn't include exclusions when * is not used."""
    sql = """
    SELECT d.id, d.filename, c.name
    FROM public.documents d
    JOIN public.clients c ON d.client_id = c.id
    WHERE business_id = :business_id
      AND d.business_id = :business_id
      AND c.business_id = :business_id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Should not have star expansion
    assert "star_expanded" not in guard_flags
    assert metadata["star"]["star_expanded"] is False

    # Should not have any exclusions recorded
    assert len(metadata["star"]["excluded"]) == 0

    # Should keep original column selection
    assert "d.id" in final_sql
    assert "d.filename" in final_sql
    assert "c.name" in final_sql


@pytest.mark.integration
def test_exclusions_metadata_structure(test_engine):
    """Test that exclusions metadata has the expected structure."""
    # Add test columns to verify all exclusion types
    with test_engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS test_bytea bytea,
            ADD COLUMN IF NOT EXISTS secret_data text
        """))

    sql = "SELECT * FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id, engine=test_engine)

    # Check metadata structure
    assert "star" in metadata
    star_info = metadata["star"]
    assert "star_expanded" in star_info
    assert "excluded" in star_info

    # Check table-specific exclusions structure
    docs_exclusions = star_info["excluded"].get("public.documents", {})

    # Should have all three exclusion categories
    assert "excluded_by_type" in docs_exclusions
    assert "excluded_by_name_pattern" in docs_exclusions
    assert "excluded_by_explicit" in docs_exclusions

    # Verify specific exclusions
    assert "test_bytea" in docs_exclusions["excluded_by_type"]
    assert "secret_data" in docs_exclusions["excluded_by_name_pattern"]
    assert "file_url" in docs_exclusions["excluded_by_explicit"]

    # Each category should be a list
    assert isinstance(docs_exclusions["excluded_by_type"], list)
    assert isinstance(docs_exclusions["excluded_by_name_pattern"], list)
    assert isinstance(docs_exclusions["excluded_by_explicit"], list)