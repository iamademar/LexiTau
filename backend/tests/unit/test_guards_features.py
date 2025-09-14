"""Unit tests for SQL feature policy guard functionality."""
import pytest
from unittest.mock import patch

from app.services.vanna_service import guard_and_rewrite_sql, GuardError


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_simple_select(mock_get_settings):
    """Test that simple SELECT queries pass feature policy checks."""
    # Mock settings
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = []
    mock_get_settings.return_value = mock_settings

    sql = "SELECT id, name FROM public.documents"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_union_operation(mock_get_settings):
    """Test that UNION operations are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT id FROM public.documents
    UNION
    SELECT id FROM public.clients
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "set_operations_disallowed"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_union_all_operation(mock_get_settings):
    """Test that UNION ALL operations are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT name FROM public.documents
    UNION ALL
    SELECT name FROM public.clients
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "set_operations_disallowed"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_intersect_operation(mock_get_settings):
    """Test that INTERSECT operations are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT id FROM public.documents
    INTERSECT
    SELECT client_id FROM public.clients
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "set_operations_disallowed"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_except_operation(mock_get_settings):
    """Test that EXCEPT operations are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT id FROM public.documents
    EXCEPT
    SELECT client_id FROM public.clients
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "set_operations_disallowed"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_lateral_join(mock_get_settings):
    """Test that LATERAL joins are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.line_items"]
    mock_settings.vanna_function_denylist = []
    mock_get_settings.return_value = mock_settings

    sql = """
    SELECT d.id, li.item_name
    FROM public.documents d
    JOIN LATERAL (
        SELECT item_name FROM public.line_items
        WHERE document_id = d.id LIMIT 5
    ) li ON true
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "lateral_joins_disallowed"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_with_recursive(mock_get_settings):
    """Test that WITH RECURSIVE is rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.categories"]
    mock_settings.vanna_function_denylist = []
    mock_get_settings.return_value = mock_settings

    sql = """
    WITH RECURSIVE category_tree AS (
        SELECT id, parent_id, name FROM public.categories WHERE parent_id IS NULL
        UNION ALL
        SELECT c.id, c.parent_id, c.name
        FROM public.categories c
        JOIN category_tree ct ON c.parent_id = ct.id
    )
    SELECT * FROM category_tree
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "with_recursive_disallowed"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_regular_cte(mock_get_settings):
    """Test that regular (non-recursive) CTEs are allowed."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = []
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


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_pg_sleep_function(mock_get_settings):
    """Test that pg_sleep function is rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = [r"^pg_sleep(?:_for|_until)?$"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT pg_sleep(5), id FROM public.documents"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "function_denied:pg_sleep"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_dblink_function(mock_get_settings):
    """Test that dblink functions are rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = [r"^dblink.*$"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT * FROM dblink('host=remote', 'SELECT 1') AS t(x int)"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "function_denied:dblink"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_pg_read_file_function(mock_get_settings):
    """Test that pg_read_file function is rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = [r"^pg_(?:read|read_binary|write|stat)_file$"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT pg_read_file('/etc/passwd')"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "function_denied:pg_read_file"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_set_config_function(mock_get_settings):
    """Test that set_config function is rejected."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = [r"^set_config$"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT set_config('work_mem', '1GB', false), id FROM public.documents"
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "function_denied:set_config"


@patch('app.services.vanna_service.get_settings')
def test_guard_accepts_allowed_functions(mock_get_settings):
    """Test that standard allowed functions pass through."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = [r"^pg_sleep$", r"^dblink.*$"]
    mock_get_settings.return_value = mock_settings

    sql = "SELECT COUNT(*), MAX(created_at), COALESCE(name, 'Unknown') FROM public.documents"
    business_id = 1

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, business_id)

    assert final_sql == sql
    assert isinstance(guard_flags, list)
    assert isinstance(metadata, dict)


@patch('app.services.vanna_service.get_settings')
def test_guard_function_denylist_case_insensitive(mock_get_settings):
    """Test that function deny-list matching is case insensitive."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents"]
    mock_settings.vanna_function_denylist = [r"^PG_SLEEP$"]  # Uppercase pattern
    mock_get_settings.return_value = mock_settings

    sql = "SELECT pg_sleep(1), id FROM public.documents"  # lowercase function
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    assert str(exc_info.value) == "function_denied:pg_sleep"


@patch('app.services.vanna_service.get_settings')
def test_guard_rejects_multiple_violations(mock_get_settings):
    """Test that the first violation found is reported (set operations take precedence)."""
    mock_settings = type('Settings', (), {})()
    mock_settings.vanna_allowed_schemas = ["public"]
    mock_settings.vanna_allowed_tables = ["public.documents", "public.clients"]
    mock_settings.vanna_function_denylist = [r"^pg_sleep$"]
    mock_get_settings.return_value = mock_settings

    # This SQL has both UNION (set operation) and pg_sleep (denied function)
    sql = """
    SELECT pg_sleep(1), id FROM public.documents
    UNION
    SELECT 0, id FROM public.clients
    """
    business_id = 1

    with pytest.raises(GuardError) as exc_info:
        guard_and_rewrite_sql(sql, business_id)

    # Set operations are checked before function deny-list, so we expect this error first
    assert str(exc_info.value) == "set_operations_disallowed"