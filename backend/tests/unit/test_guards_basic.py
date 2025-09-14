"""Unit tests for basic SQL guard functionality."""
import pytest

from app.services.vanna_service import guard_and_rewrite_sql, GuardError


def test_guard_accepts_simple_select():
    """Test that a simple SELECT statement passes guards."""
    sql = "SELECT id, name FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql  # For now, should return original
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


def test_guard_rejects_insert():
    """Test that INSERT statements are rejected."""
    sql = "INSERT INTO public.documents (name) VALUES ('test')"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "non_select_statement"


def test_guard_rejects_update():
    """Test that UPDATE statements are rejected."""
    sql = "UPDATE public.documents SET name = 'updated' WHERE id = 1"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "non_select_statement"


def test_guard_rejects_delete():
    """Test that DELETE statements are rejected."""
    sql = "DELETE FROM public.documents WHERE id = 1"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "non_select_statement"


def test_guard_rejects_create_table():
    """Test that CREATE TABLE statements are rejected."""
    sql = "CREATE TABLE test_table (id INT, name TEXT)"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "non_select_statement"


def test_guard_rejects_drop_table():
    """Test that DROP TABLE statements are rejected."""
    sql = "DROP TABLE test_table"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "non_select_statement"


def test_guard_handles_malformed_sql():
    """Test that malformed SQL raises GuardError."""
    sql = "SELECT FROM WHERE"  # Invalid SQL
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    error_msg = str(exc_info.value)
    assert "sql_parse_error" in error_msg


def test_guard_handles_empty_sql():
    """Test that empty SQL raises GuardError."""
    sql = ""
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "failed_to_parse_sql"


def test_guard_accepts_select_with_joins():
    """Test that SELECT with JOINs passes guards."""
    sql = """
    SELECT d.id, d.name, c.name as client_name
    FROM public.documents d
    JOIN public.clients c ON d.client_id = c.id
    WHERE business_id = :business_id
      AND d.business_id = :business_id
      AND c.business_id = :business_id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


def test_guard_accepts_select_with_subquery():
    """Test that SELECT with subqueries passes guards."""
    sql = """
    SELECT id, name
    FROM public.documents
    WHERE business_id = :business_id
      AND documents.business_id = :business_id
      AND client_id IN (SELECT id FROM public.clients WHERE business_id = :business_id AND clients.business_id = :business_id AND active = true)
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)