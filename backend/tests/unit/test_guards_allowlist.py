"""Unit tests for schema/table allow-list guard functionality."""
import pytest
from unittest.mock import patch

from app.services.vanna_service import guard_and_rewrite_sql, GuardError


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_allowed_table(mock_get_settings):
    """Test that queries on allowed tables pass guards."""
    # Mock settings
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = False
    mock_settings.vanna_tenant_required_tables = []
    mock_get_settings.return_value = mock_settings

    sql = "SELECT id, name FROM public.documents WHERE business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_allowed_table_without_schema(mock_get_settings):
    """Test that queries on allowed tables work without explicit schema (defaults to public)."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = False
    mock_settings.vanna_tenant_required_tables = []
    mock_get_settings.return_value = mock_settings

    sql = "SELECT id, name FROM documents WHERE business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_join_on_allowed_tables(mock_get_settings):
    """Test that joins between allowed tables pass guards."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, d.name, c.name as client_name
    FROM public.documents d
    JOIN public.clients c ON d.client_id = c.id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_information_schema_access(mock_get_settings):
    """Test that queries on information_schema are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT table_name FROM information_schema.tables"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "schema_not_allowed:information_schema"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_pg_catalog_access(mock_get_settings):
    """Test that queries on pg_catalog are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT schemaname FROM pg_catalog.pg_tables"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "schema_not_allowed:pg_catalog"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_non_allowed_table_in_public(mock_get_settings):
    """Test that queries on non-allowed tables in public schema are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT * FROM public.users"  # users not in allowed list
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "table_not_allowed:public.users"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_non_allowed_table_without_schema(mock_get_settings):
    """Test that queries on non-allowed tables without schema prefix are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT * FROM users"  # users not in allowed list, defaults to public.users
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "table_not_allowed:public.users"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_cross_schema_join(mock_get_settings):
    """Test that cross-schema joins are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public", "other_schema"]
    mock_settings.vanna_allowed_tables = [
        "public.documents", "public.clients",
        "other_schema.reports"
    ]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, r.name
    FROM public.documents d
    JOIN other_schema.reports r ON d.id = r.doc_id
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "cross_schema_join"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_subquery_with_allowed_tables(mock_get_settings):
    """Test that subqueries with allowed tables pass guards."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT id, name
    FROM public.documents
    WHERE client_id IN (SELECT id FROM public.clients WHERE active = true)
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_subquery_with_non_allowed_table(mock_get_settings):
    """Test that subqueries with non-allowed tables are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT id, name
    FROM public.documents
    WHERE client_id IN (SELECT id FROM public.users WHERE active = true)
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "table_not_allowed:public.users"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_cte_with_allowed_tables(mock_get_settings):
    """Test that CTEs with allowed tables pass guards."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = """
    WITH active_clients AS (
        SELECT id FROM public.clients WHERE active = true
    )
    SELECT d.id, d.name
    FROM public.documents d
    JOIN active_clients ac ON d.client_id = ac.id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)