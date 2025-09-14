"""Unit tests for ORDER BY and LIMIT injection functionality."""
import pytest
from unittest.mock import Mock, patch
import sqlglot

from app.services.vanna_service import (
    _inject_smart_order_by,
    _inject_limit_clause,
    guard_and_rewrite_sql,
    guarded_run_sql,
    GuardError
)


class MockSettings:
    """Mock settings for testing."""
    vanna_default_row_limit = 500
    vanna_tenant_required_tables = [
        "public.documents", "public.clients", "public.projects"
    ]
    vanna_allowed_schemas = ["public"]
    vanna_allowed_tables = [
        "public.documents", "public.clients", "public.projects",
        "public.line_items", "public.extracted_fields", "public.categories"
    ]
    vanna_tenant_column = "business_id"
    vanna_tenant_param = "business_id"
    vanna_tenant_enforce_per_table = True
    vanna_expand_select_star = True
    vanna_expand_exclude_types = ["bytea"]
    vanna_expand_exclude_name_patterns = ["password", "secret", "api[_-]?key", "token"]
    vanna_expand_exclude_columns = ["public.documents.file_url"]
    vanna_function_denylist = []
    vanna_audit_enabled = True
    vanna_audit_redact = False
    vanna_always_200_on_errors = False


@pytest.fixture
def mock_settings():
    return MockSettings()


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine."""
    engine = Mock()
    return engine


def test_inject_order_by_existing_order_clause(mock_engine, mock_settings):
    """Test that existing ORDER BY clause is preserved."""
    sql = "SELECT * FROM documents ORDER BY created_at DESC"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is False
    assert order_info["order_strategy"] == "existing"
    assert order_info["order_expression"] is None

    # Verify ORDER BY clause is still there
    assert result_statement.args.get("order") is not None


def test_inject_order_by_group_by_present(mock_engine, mock_settings):
    """Test ORDER BY injection when GROUP BY is present."""
    sql = "SELECT client_id, COUNT(*) FROM documents GROUP BY client_id"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is True
    assert order_info["order_strategy"] == "group_by_first"
    assert "client_id" in order_info["order_expression"]

    # Verify ORDER BY clause was added and check the SQL output
    order_clause = result_statement.args.get("order")
    assert order_clause is not None
    assert len(order_clause.expressions) == 1

    # Check the generated SQL contains ASC (or no DESC)
    final_sql = result_statement.sql(dialect='postgres')
    assert "ORDER BY" in final_sql
    assert "DESC" not in final_sql or "ASC" in final_sql


def test_inject_order_by_distinct_present(mock_engine, mock_settings):
    """Test ORDER BY injection when DISTINCT is present."""
    sql = "SELECT DISTINCT client_id FROM documents"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is True
    assert order_info["order_strategy"] == "distinct_first_column"
    assert order_info["order_expression"] == "1 ASC"

    # Verify ORDER BY 1 ASC was added
    order_clause = result_statement.args.get("order")
    assert order_clause is not None
    assert len(order_clause.expressions) == 1

    # Check the generated SQL contains ORDER BY 1 and no DESC
    final_sql = result_statement.sql(dialect='postgres')
    assert "ORDER BY 1" in final_sql
    assert "DESC" not in final_sql


def test_inject_order_by_tenant_table_heuristic(mock_engine, mock_settings):
    """Test ORDER BY injection using tenant table heuristic."""
    sql = "SELECT * FROM documents d WHERE business_id = :business_id"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    # Mock column lookup to return created_at
    with patch('app.services.vanna_service._get_table_columns_from_db') as mock_get_cols:
        mock_get_cols.return_value = (
            [('id', 'int'), ('created_at', 'timestamp'), ('filename', 'text')],
            {}
        )

        result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is True
    assert order_info["order_strategy"] == "tenant_table_heuristic"
    assert "created_at DESC" in order_info["order_expression"]

    # Verify ORDER BY clause was added with DESC
    order_clause = result_statement.args.get("order")
    assert order_clause is not None
    assert len(order_clause.expressions) == 1

    # Check the generated SQL contains DESC
    final_sql = result_statement.sql(dialect='postgres')
    assert "ORDER BY" in final_sql
    assert "DESC" in final_sql


def test_inject_order_by_fallback_first_column(mock_engine, mock_settings):
    """Test ORDER BY injection fallback to first column."""
    sql = "SELECT * FROM documents d WHERE business_id = :business_id"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    # Mock column lookup to return no standard columns
    with patch('app.services.vanna_service._get_table_columns_from_db') as mock_get_cols:
        mock_get_cols.return_value = (
            [('custom_field', 'text'), ('another_field', 'int')],
            {}
        )

        result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is True
    assert order_info["order_strategy"] == "fallback_first_column"
    assert order_info["order_expression"] == "1 ASC"


def test_inject_order_by_column_lookup_failure(mock_engine, mock_settings):
    """Test ORDER BY injection when column lookup fails."""
    sql = "SELECT * FROM documents d WHERE business_id = :business_id"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    # Mock column lookup to raise exception
    with patch('app.services.vanna_service._get_table_columns_from_db') as mock_get_cols:
        mock_get_cols.side_effect = Exception("Database error")

        result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is True
    assert order_info["order_strategy"] == "fallback_first_column"
    assert order_info["order_expression"] == "1 ASC"


def test_inject_limit_existing_limit_clause(mock_settings):
    """Test that existing LIMIT clause is preserved."""
    sql = "SELECT * FROM documents LIMIT 100"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    result_statement, limit_info = _inject_limit_clause(statement, mock_settings)

    assert limit_info["limit_injected"] is False
    assert limit_info["limit_value"] == "existing"

    # Verify LIMIT clause is still there
    assert result_statement.args.get("limit") is not None


def test_inject_limit_missing_limit_clause(mock_settings):
    """Test LIMIT injection when no LIMIT clause exists."""
    sql = "SELECT * FROM documents WHERE business_id = :business_id"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    result_statement, limit_info = _inject_limit_clause(statement, mock_settings)

    assert limit_info["limit_injected"] is True
    assert limit_info["limit_value"] == 501  # row_limit + 1

    # Verify LIMIT clause was added
    limit_clause = result_statement.args.get("limit")
    assert limit_clause is not None
    assert limit_clause.expression.this == "501"


def test_guarded_run_sql_truncation_detection(mock_engine):
    """Test truncation detection in guarded_run_sql."""
    # Mock the database connection and results
    mock_conn = Mock()
    mock_result = Mock()

    # Simulate 6 rows returned when limit is 5
    mock_result.keys.return_value = ["id", "name"]
    mock_result.fetchall.return_value = [
        (1, "row1"), (2, "row2"), (3, "row3"),
        (4, "row4"), (5, "row5"), (6, "row6")
    ]

    mock_conn.execute.return_value = mock_result
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine.begin.return_value = mock_conn

    # Call with row_limit=5 (should truncate and mark as truncated)
    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        mock_engine, "SELECT * FROM test LIMIT 6", {}, row_limit=5
    )

    assert len(rows) == 5  # Truncated to 5 rows
    assert row_count == 5
    assert truncated is True
    assert len(columns) == 2


def test_guarded_run_sql_no_truncation(mock_engine):
    """Test no truncation when result count is within limit."""
    # Mock the database connection and results
    mock_conn = Mock()
    mock_result = Mock()

    # Simulate 3 rows returned when limit is 5
    mock_result.keys.return_value = ["id", "name"]
    mock_result.fetchall.return_value = [(1, "row1"), (2, "row2"), (3, "row3")]

    mock_conn.execute.return_value = mock_result
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine.begin.return_value = mock_conn

    # Call with row_limit=5 (should not truncate)
    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        mock_engine, "SELECT * FROM test", {}, row_limit=5
    )

    assert len(rows) == 3
    assert row_count == 3
    assert truncated is False


def test_guarded_run_sql_no_row_limit(mock_engine):
    """Test guarded_run_sql when no row_limit is provided."""
    # Mock the database connection and results
    mock_conn = Mock()
    mock_result = Mock()

    mock_result.keys.return_value = ["id", "name"]
    mock_result.fetchall.return_value = [(1, "row1"), (2, "row2")]

    mock_conn.execute.return_value = mock_result
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine.begin.return_value = mock_conn

    # Call without row_limit (should never truncate)
    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        mock_engine, "SELECT * FROM test", {}
    )

    assert len(rows) == 2
    assert row_count == 2
    assert truncated is False


@patch('app.services.vanna_service.get_settings')
@patch('app.services.vanna_service._get_table_columns_from_db')
@patch('app.services.vanna_service._extract_table_aliases')
def test_guard_and_rewrite_sql_integration(mock_extract_aliases, mock_get_cols, mock_get_settings, mock_engine):
    """Test full integration of ORDER BY and LIMIT injection in guard_and_rewrite_sql."""
    # Setup mocks
    mock_settings_instance = MockSettings()
    mock_get_settings.return_value = mock_settings_instance
    mock_extract_aliases.return_value = {"documents": ("public", "documents")}
    mock_get_cols.return_value = (
        [('id', 'int'), ('created_at', 'timestamp'), ('filename', 'text')],
        {}
    )

    # Test SQL without ORDER BY or LIMIT
    sql = "SELECT * FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id"

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, 1, engine=mock_engine)

    # Check that both ORDER BY and LIMIT were injected
    assert "order_injected" in guard_flags
    assert "limit_injected" in guard_flags
    assert "ORDER BY" in final_sql
    assert "LIMIT" in final_sql
    assert "501" in final_sql  # row_limit + 1

    # Check metadata
    assert "order" in metadata
    assert "limit" in metadata
    assert metadata["order"]["order_injected"] is True
    assert metadata["limit"]["limit_injected"] is True
    assert metadata["limit"]["limit_value"] == 501


@patch('app.services.vanna_service.get_settings')
def test_guard_and_rewrite_sql_preserves_existing_clauses(mock_get_settings, mock_engine):
    """Test that existing ORDER BY and LIMIT clauses are preserved."""
    mock_settings_instance = MockSettings()
    mock_get_settings.return_value = mock_settings_instance

    # Test SQL with existing ORDER BY and LIMIT
    sql = "SELECT * FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id ORDER BY filename ASC LIMIT 10"

    final_sql, guard_flags, metadata = guard_and_rewrite_sql(sql, 1, engine=mock_engine)

    # Check that neither was injected
    assert "order_injected" not in guard_flags
    assert "limit_injected" not in guard_flags
    assert "ORDER BY filename ASC" in final_sql
    assert "LIMIT 10" in final_sql

    # Check metadata
    assert metadata["order"]["order_injected"] is False
    assert metadata["limit"]["limit_injected"] is False


def test_inject_order_by_tenant_table_priority():
    """Test that tenant-bearing tables get priority for ORDER BY heuristics."""
    mock_engine = Mock()
    mock_settings = MockSettings()

    # SQL with multiple tables, first is not tenant-bearing
    sql = """
    SELECT * FROM public.categories c
    JOIN public.documents d ON c.id = d.category_id
    WHERE business_id = :business_id
    """
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    with patch('app.services.vanna_service._extract_table_aliases') as mock_aliases:
        with patch('app.services.vanna_service._get_table_columns_from_db') as mock_get_cols:
            # Mock table aliases - categories first, documents second
            mock_aliases.return_value = {
                "c": ("public", "categories"),
                "d": ("public", "documents")
            }

            # Mock columns for documents table (tenant-bearing)
            mock_get_cols.return_value = (
                [('id', 'int'), ('created_at', 'timestamp'), ('filename', 'text')],
                {}
            )

            result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    # Should use documents (tenant table) for ORDER BY, not categories
    assert order_info["order_injected"] is True
    assert order_info["order_strategy"] == "tenant_table_heuristic"
    assert "d.created_at DESC" in order_info["order_expression"]


def test_inject_order_by_column_priority():
    """Test that columns are tried in correct priority order."""
    mock_engine = Mock()
    mock_settings = MockSettings()

    sql = "SELECT * FROM documents d WHERE business_id = :business_id"
    statement = sqlglot.parse(sql, dialect='postgres')[0]

    # Test that issued_on is preferred over id when both exist
    with patch('app.services.vanna_service._get_table_columns_from_db') as mock_get_cols:
        mock_get_cols.return_value = (
            [('id', 'int'), ('issued_on', 'timestamp'), ('filename', 'text')],
            {}
        )

        result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is True
    assert "issued_on DESC" in order_info["order_expression"]  # Should pick issued_on, not id

    # Test that id is used when no other priority columns exist
    with patch('app.services.vanna_service._get_table_columns_from_db') as mock_get_cols:
        mock_get_cols.return_value = (
            [('id', 'int'), ('filename', 'text'), ('custom_field', 'text')],
            {}
        )

        result_statement, order_info = _inject_smart_order_by(statement, mock_engine, mock_settings)

    assert order_info["order_injected"] is True
    assert "id ASC" in order_info["order_expression"]  # Should pick id in ASC order