"""Unit tests for tenant scope enforcement guard functionality."""
import pytest
from unittest.mock import patch

from app.services.vanna_service import guard_and_rewrite_sql, GuardError


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_sql_with_global_tenant(mock_get_settings):
    """Test that SQL with global tenant predicate passes validation."""
    # Mock settings
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
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
def test_guard_rejects_sql_missing_global_tenant(mock_get_settings):
    """Test that SQL without global tenant predicate is rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = False
    mock_settings.vanna_tenant_required_tables = []
    mock_get_settings.return_value = mock_settings

    sql = "SELECT id, name FROM public.documents"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "missing_tenant_scope"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_global_tenant_with_whitespace(mock_get_settings):
    """Test that global tenant predicate with various whitespace patterns is accepted."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = False
    mock_settings.vanna_tenant_required_tables = []
    mock_get_settings.return_value = mock_settings

    # Test with extra whitespace
    sql = "SELECT id FROM public.documents WHERE business_id  =  :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_global_tenant_case_insensitive(mock_get_settings):
    """Test that global tenant predicate matching is case insensitive."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = False
    mock_settings.vanna_tenant_required_tables = []
    mock_get_settings.return_value = mock_settings

    # Test with uppercase column name
    sql = "SELECT id FROM public.documents WHERE BUSINESS_ID = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_per_alias_tenant_single_table(mock_get_settings):
    """Test that per-alias tenant enforcement works for single table with alias."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, d.name
    FROM public.documents d
    WHERE business_id = :business_id AND d.business_id = :business_id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_missing_per_alias_tenant(mock_get_settings):
    """Test that missing per-alias tenant predicate is rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents"]
    mock_get_settings.return_value = mock_settings

    # Has global tenant but missing per-alias tenant for 'd' alias
    sql = """
    SELECT d.id, d.name
    FROM public.documents d
    WHERE business_id = :business_id
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "missing_tenant_scope_for_alias:d"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_join_with_both_aliases_filtered(mock_get_settings):
    """Test that join with both aliases having tenant predicates passes."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, c.name
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


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_join_with_only_one_alias_filtered(mock_get_settings):
    """Test that join where only one side is filtered is rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    # Missing per-alias tenant for 'c' alias
    sql = """
    SELECT d.id, c.name
    FROM public.documents d
    JOIN public.clients c ON d.client_id = c.id
    WHERE business_id = :business_id
      AND d.business_id = :business_id
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "missing_tenant_scope_for_alias:c"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_table_without_alias_using_table_name(mock_get_settings):
    """Test that table without explicit alias uses table name for tenant checking."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT documents.id
    FROM public.documents
    WHERE business_id = :business_id AND documents.business_id = :business_id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_table_without_alias_missing_tenant(mock_get_settings):
    """Test that table without explicit alias is rejected when missing per-table tenant."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents"]
    mock_get_settings.return_value = mock_settings

    # Missing per-alias tenant for 'documents' table name
    sql = """
    SELECT documents.id
    FROM public.documents
    WHERE business_id = :business_id
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "missing_tenant_scope_for_alias:documents"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_per_table_enforcement_disabled(mock_get_settings):
    """Test that per-table enforcement can be disabled."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = False  # Disabled
    mock_settings.vanna_tenant_required_tables = ["public.documents"]
    mock_get_settings.return_value = mock_settings

    # Only global tenant, no per-alias tenant
    sql = "SELECT d.id FROM public.documents d WHERE business_id = :business_id"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_non_required_table_without_per_alias_tenant(mock_get_settings):
    """Test that non-required tables don't need per-alias tenant predicates."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.categories"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents"]  # categories not required
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, c.name
    FROM public.documents d
    JOIN public.categories c ON d.category_id = c.id
    WHERE business_id = :business_id
      AND d.business_id = :business_id
    """
    # Note: categories (c) doesn't have per-alias tenant, but it's not in required_tables
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_tenant_in_join_condition(mock_get_settings):
    """Test that tenant predicate in JOIN ON clause is recognized."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, c.name
    FROM public.documents d
    JOIN public.clients c ON d.client_id = c.id
        AND d.business_id = :business_id
        AND c.business_id = :business_id
    WHERE business_id = :business_id
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_subquery_with_tenant_predicates(mock_get_settings):
    """Test that subqueries with proper tenant predicates pass validation."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_settings.vanna_tenant_column = "business_id"
    mock_settings.vanna_tenant_param = "business_id"
    mock_settings.vanna_tenant_enforce_per_table = True
    mock_settings.vanna_tenant_required_tables = ["public.documents", "public.clients"]
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, d.name
    FROM public.documents d
    WHERE d.business_id = :business_id
      AND business_id = :business_id
      AND d.client_id IN (
          SELECT c.id FROM public.clients c
          WHERE c.business_id = :business_id AND c.active = true
      )
    """
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)