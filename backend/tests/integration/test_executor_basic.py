"""Integration tests for the guarded SQL executor."""
import pytest
import time
from sqlalchemy.exc import OperationalError, InternalError

from app.services.vanna_service import guarded_run_sql
from tests.integration.conftest import engine


@pytest.mark.integration
def test_basic_select_execution():
    """Test basic SELECT execution via guarded_run_sql."""
    sql = "SELECT 1 as test_value"
    params = {}

    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )

    # Assert basic structure
    assert columns == ["test_value"]
    assert rows == [[1]]
    assert row_count == 1
    assert truncated is False
    assert execution_ms >= 0
    assert isinstance(execution_ms, int)


@pytest.mark.integration
def test_parameterized_query():
    """Test parameterized query execution."""
    sql = "SELECT :value1 as col1, :value2 as col2"
    params = {"value1": "hello", "value2": 42}

    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )

    assert columns == ["col1", "col2"]
    assert rows == [["hello", 42]]
    assert row_count == 1


@pytest.mark.integration
def test_multiple_rows():
    """Test query returning multiple rows."""
    sql = """
    SELECT generate_series(1, 3) as num,
           'row_' || generate_series(1, 3)::text as label
    """
    params = {}

    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )

    assert columns == ["num", "label"]
    assert row_count == 3
    assert rows == [[1, "row_1"], [2, "row_2"], [3, "row_3"]]


@pytest.mark.integration
def test_empty_result_set():
    """Test query returning empty result set."""
    sql = "SELECT 'test' as col WHERE 1=0"
    params = {}

    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )

    assert columns == ["col"]
    assert rows == []
    assert row_count == 0
    assert truncated is False


@pytest.mark.integration
def test_safety_gucs_read_only():
    """Test that transaction is read-only - should fail on INSERT."""
    sql = "CREATE TEMP TABLE test_table (id INT)"
    params = {}

    # Try to execute the DDL command
    operation_failed = False
    error_message = ""
    
    try:
        guarded_run_sql(engine, sql, params)
    except (OperationalError, InternalError) as e:
        operation_failed = True
        error_message = str(e).lower()

    # Verify the operation failed with the correct error
    assert operation_failed, "The operation should have failed but succeeded"
    assert "read-only transaction" in error_message, f"Expected read-only transaction error, got: {error_message}"


@pytest.mark.integration
def test_timeout_functionality():
    """Test statement timeout functionality with slow query."""
    # Use a query that should take longer than the timeout
    # generate_series with pg_sleep_for should trigger timeout
    sql = """
    SELECT pg_sleep(0.1), generate_series(1, 10) as num
    """
    params = {}

    # Set very short timeout
    timeout_s = 0.05  # 50ms

    # Should timeout
    with pytest.raises(OperationalError) as exc_info:
        guarded_run_sql(engine, sql, params, timeout_s=timeout_s)

    # Check it's a timeout error
    error_msg = str(exc_info.value).lower()
    assert any(keyword in error_msg for keyword in ["timeout", "cancelled", "query_canceled"])


@pytest.mark.integration
def test_work_mem_setting():
    """Test that work_mem setting is applied."""
    sql = "SHOW work_mem"
    params = {}

    # Test with custom work_mem
    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params, work_mem="32MB"
    )

    assert columns == ["work_mem"]
    assert rows[0][0] == "32MB"


@pytest.mark.integration
def test_search_path_setting():
    """Test that search_path is set to public."""
    sql = "SHOW search_path"
    params = {}

    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )

    assert columns == ["search_path"]
    # Should be just "public"
    assert rows[0][0] == "public"


@pytest.mark.integration
def test_execution_timing():
    """Test that execution timing is reasonable."""
    sql = "SELECT 1"
    params = {}

    start_time = time.time()
    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )
    actual_time_ms = (time.time() - start_time) * 1000

    # Execution time should be in reasonable range
    assert execution_ms >= 0  # Allow 0 for very fast queries
    assert execution_ms < actual_time_ms + 100  # Allow some overhead
    assert execution_ms < 5000  # Should be under 5 seconds for simple query


@pytest.mark.integration
def test_null_values_handling():
    """Test handling of NULL values in results."""
    sql = "SELECT NULL as null_col, 'not_null' as text_col, 42 as int_col"
    params = {}

    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )

    assert columns == ["null_col", "text_col", "int_col"]
    assert rows == [[None, "not_null", 42]]
    assert row_count == 1


@pytest.mark.integration
def test_different_data_types():
    """Test handling of various PostgreSQL data types."""
    sql = """
    SELECT
        42::integer as int_val,
        'hello'::text as text_val,
        true::boolean as bool_val,
        3.14::decimal as decimal_val,
        '2023-01-01'::date as date_val
    """
    params = {}

    columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
        engine, sql, params
    )

    assert columns == ["int_val", "text_val", "bool_val", "decimal_val", "date_val"]
    assert len(rows) == 1
    row = rows[0]

    assert row[0] == 42  # integer
    assert row[1] == "hello"  # text
    assert row[2] is True  # boolean
    # decimal and date values will be handled by SQLAlchemy's type system
    assert row[3] is not None  # decimal
    assert row[4] is not None  # date