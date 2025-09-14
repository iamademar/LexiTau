"""Unit tests for JSON serialization and metadata functionality."""
import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID, uuid4
from sqlalchemy import Engine, text

from app.services.vanna_service import serialize_cell, build_columns_meta


class TestSerializeCell:
    """Test cases for serialize_cell function."""

    def test_serialize_none(self):
        """Test that None values pass through unchanged."""
        assert serialize_cell(None) is None

    def test_serialize_decimal(self):
        """Test Decimal serialization to string."""
        decimal_val = Decimal('123.456')
        result = serialize_cell(decimal_val)
        assert result == '123.456'
        assert isinstance(result, str)

    def test_serialize_int_small(self):
        """Test small integer values pass through unchanged."""
        small_int = 42
        result = serialize_cell(small_int)
        assert result == 42
        assert isinstance(result, int)

    def test_serialize_int_max_safe(self):
        """Test integer at JavaScript MAX_SAFE_INTEGER boundary."""
        max_safe = 2**53 - 1  # 9007199254740991
        result = serialize_cell(max_safe)
        assert result == max_safe
        assert isinstance(result, int)

    def test_serialize_int_beyond_max_safe_positive(self):
        """Test large positive integer converts to string."""
        large_int = 2**53  # Beyond MAX_SAFE_INTEGER
        result = serialize_cell(large_int)
        assert result == str(large_int)
        assert isinstance(result, str)

    def test_serialize_int_beyond_max_safe_negative(self):
        """Test large negative integer converts to string."""
        large_neg_int = -(2**53)  # Beyond MAX_SAFE_INTEGER
        result = serialize_cell(large_neg_int)
        assert result == str(large_neg_int)
        assert isinstance(result, str)

    def test_serialize_datetime(self):
        """Test datetime serialization to ISO-8601 with Z suffix."""
        dt = datetime(2023, 12, 25, 15, 30, 45, 123456)
        result = serialize_cell(dt)
        assert result == '2023-12-25T15:30:45.123456Z'
        assert isinstance(result, str)

    def test_serialize_date(self):
        """Test date serialization to YYYY-MM-DD format."""
        d = date(2023, 12, 25)
        result = serialize_cell(d)
        assert result == '2023-12-25'
        assert isinstance(result, str)

    def test_serialize_uuid(self):
        """Test UUID serialization to string."""
        uuid_val = uuid4()
        result = serialize_cell(uuid_val)
        assert result == str(uuid_val)
        assert isinstance(result, str)

    def test_serialize_list(self):
        """Test list values pass through unchanged."""
        list_val = [1, 2, 'three', None]
        result = serialize_cell(list_val)
        assert result == list_val
        assert isinstance(result, list)

    def test_serialize_tuple(self):
        """Test tuple converts to list."""
        tuple_val = (1, 2, 'three', None)
        result = serialize_cell(tuple_val)
        assert result == [1, 2, 'three', None]
        assert isinstance(result, list)

    def test_serialize_dict(self):
        """Test dict values pass through unchanged."""
        dict_val = {'key': 'value', 'num': 42}
        result = serialize_cell(dict_val)
        assert result == dict_val
        assert isinstance(result, dict)

    def test_serialize_other_types(self):
        """Test other types pass through unchanged."""
        # Test string
        string_val = "hello world"
        assert serialize_cell(string_val) == string_val

        # Test bool
        bool_val = True
        assert serialize_cell(bool_val) == bool_val

        # Test float
        float_val = 3.14159
        assert serialize_cell(float_val) == float_val


class TestBuildColumnsMeta:
    """Test cases for build_columns_meta function."""

    @pytest.fixture
    def mock_engine(self):
        """Mock SQLAlchemy engine."""
        engine = Mock(spec=Engine)
        return engine

    def test_empty_columns_and_rows(self, mock_engine):
        """Test with empty columns and rows."""
        result = build_columns_meta(mock_engine, [], [], None)
        assert result == []

    def test_single_column_all_null(self, mock_engine):
        """Test column with all null values."""
        columns = ['nullable_col']
        rows = [[None], [None], [None]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        assert len(result) == 1
        meta = result[0]
        assert meta['name'] == 'nullable_col'
        assert meta['py_type'] == 'NoneType'
        assert meta['nullable'] is True
        assert meta['serialized_as'] == 'NoneType'
        assert meta['db_type'] == 'unknown'

    def test_single_column_no_nulls(self, mock_engine):
        """Test column with no null values."""
        columns = ['int_col']
        rows = [[1], [2], [3]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        assert len(result) == 1
        meta = result[0]
        assert meta['name'] == 'int_col'
        assert meta['py_type'] == 'int'
        assert meta['nullable'] is False
        assert meta['serialized_as'] == 'int'
        assert meta['db_type'] == 'unknown'

    def test_mixed_null_and_values(self, mock_engine):
        """Test column with mixed null and non-null values."""
        columns = ['mixed_col']
        rows = [[None], ['hello'], [None], ['world']]

        result = build_columns_meta(mock_engine, columns, rows, None)

        assert len(result) == 1
        meta = result[0]
        assert meta['name'] == 'mixed_col'
        assert meta['py_type'] == 'str'  # First non-null determines type
        assert meta['nullable'] is True
        assert meta['serialized_as'] == 'str'

    def test_decimal_column(self, mock_engine):
        """Test Decimal column metadata."""
        columns = ['price']
        rows = [[Decimal('19.99')], [Decimal('25.50')]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'Decimal'
        assert meta['serialized_as'] == 'str'

    def test_datetime_column(self, mock_engine):
        """Test datetime column metadata."""
        columns = ['created_at']
        dt = datetime(2023, 12, 25, 15, 30, 45)
        rows = [[dt], [datetime.now()]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'datetime'
        assert meta['serialized_as'] == 'str'

    def test_date_column(self, mock_engine):
        """Test date column metadata."""
        columns = ['birth_date']
        rows = [[date(1990, 5, 15)], [date(1995, 8, 22)]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'date'
        assert meta['serialized_as'] == 'str'

    def test_uuid_column(self, mock_engine):
        """Test UUID column metadata."""
        columns = ['id']
        rows = [[uuid4()], [uuid4()]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'UUID'
        assert meta['serialized_as'] == 'str'

    def test_list_column(self, mock_engine):
        """Test list column metadata."""
        columns = ['tags']
        rows = [[[1, 2, 3]], [['a', 'b']]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'list'
        assert meta['serialized_as'] == 'list'

    def test_tuple_column(self, mock_engine):
        """Test tuple column metadata."""
        columns = ['coordinates']
        rows = [[(1, 2)], [(3, 4)]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'tuple'
        assert meta['serialized_as'] == 'list'

    def test_large_integer_serialization(self, mock_engine):
        """Test large integer that should serialize as string."""
        columns = ['big_num']
        large_int = 2**53  # Beyond JavaScript MAX_SAFE_INTEGER
        rows = [[large_int], [123]]  # Mix of large and small ints

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'int'
        assert meta['serialized_as'] == 'str'  # Because one value exceeds limit

    def test_small_integers_only(self, mock_engine):
        """Test integers all within safe range."""
        columns = ['small_nums']
        rows = [[42], [123], [999]]

        result = build_columns_meta(mock_engine, columns, rows, None)

        meta = result[0]
        assert meta['py_type'] == 'int'
        assert meta['serialized_as'] == 'int'  # All values safe

    def test_multiple_columns(self, mock_engine):
        """Test metadata for multiple columns."""
        columns = ['id', 'name', 'price', 'created_at']
        rows = [
            [1, 'Product A', Decimal('19.99'), datetime(2023, 1, 1)],
            [2, 'Product B', Decimal('25.50'), datetime(2023, 1, 2)],
            [3, None, Decimal('30.00'), datetime(2023, 1, 3)]  # name is null
        ]

        result = build_columns_meta(mock_engine, columns, rows, None)

        assert len(result) == 4

        # id column
        assert result[0]['name'] == 'id'
        assert result[0]['py_type'] == 'int'
        assert result[0]['nullable'] is False

        # name column (has nulls)
        assert result[1]['name'] == 'name'
        assert result[1]['py_type'] == 'str'
        assert result[1]['nullable'] is True

        # price column
        assert result[2]['name'] == 'price'
        assert result[2]['py_type'] == 'Decimal'
        assert result[2]['serialized_as'] == 'str'

        # created_at column
        assert result[3]['name'] == 'created_at'
        assert result[3]['py_type'] == 'datetime'
        assert result[3]['serialized_as'] == 'str'

    def test_postgresql_type_lookup_success(self, mock_engine):
        """Test successful PostgreSQL type lookup via OID."""
        # Mock description with OID information
        mock_description = Mock()
        mock_description.description = [
            ('id', 23, None, None, None, None, None),  # OID 23 = int4
            ('name', 25, None, None, None, None, None)  # OID 25 = text
        ]

        # Mock database connection and query result
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [(23, 'int4'), (25, 'text')]
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine.begin.return_value = mock_conn

        columns = ['id', 'name']
        rows = [[1, 'test']]

        result = build_columns_meta(mock_engine, columns, rows, mock_description)

        assert result[0]['db_type'] == 'int4'
        assert result[1]['db_type'] == 'text'

    def test_postgresql_type_lookup_failure(self, mock_engine):
        """Test graceful handling of PostgreSQL type lookup failure."""
        # Mock description with OID information
        mock_description = Mock()
        mock_description.description = [
            ('id', 23, None, None, None, None, None),
        ]

        # Mock database connection that raises exception
        mock_engine.begin.side_effect = Exception("Database connection failed")

        columns = ['id']
        rows = [[1]]

        result = build_columns_meta(mock_engine, columns, rows, mock_description)

        # Should fallback gracefully
        assert result[0]['db_type'] == 'unknown'
        assert result[0]['py_type'] == 'int'

    def test_no_description_provided(self, mock_engine):
        """Test when no description is provided."""
        columns = ['test_col']
        rows = [['value']]

        result = build_columns_meta(mock_engine, columns, rows, None)

        assert result[0]['db_type'] == 'unknown'
        assert result[0]['py_type'] == 'str'

    def test_malformed_description(self, mock_engine):
        """Test with malformed description object."""
        # Mock description without proper structure
        mock_description = Mock()
        mock_description.description = [
            ('id',),  # Missing OID
        ]

        columns = ['id']
        rows = [[1]]

        result = build_columns_meta(mock_engine, columns, rows, mock_description)

        assert result[0]['db_type'] == 'unknown'
        assert result[0]['py_type'] == 'int'

    def test_row_length_mismatch(self, mock_engine):
        """Test handling of rows with different lengths than columns."""
        columns = ['col1', 'col2', 'col3']
        rows = [
            [1, 'a'],  # Missing col3
            [2, 'b', 'c'],  # Complete row
            [3]  # Missing col2 and col3
        ]

        result = build_columns_meta(mock_engine, columns, rows, None)

        assert len(result) == 3
        assert result[0]['py_type'] == 'int'  # col1
        assert result[1]['py_type'] == 'str'  # col2
        assert result[2]['py_type'] == 'str'  # col3 (found 'c' in row 2)
        assert result[2]['nullable'] is True  # col3 has missing values in other rows

    def test_column_with_no_values(self, mock_engine):
        """Test column where no rows have values for that column index."""
        columns = ['col1', 'col2']
        rows = [
            [1],  # Missing col2
            [2],  # Missing col2
            [3]   # Missing col2
        ]

        result = build_columns_meta(mock_engine, columns, rows, None)

        assert len(result) == 2
        assert result[0]['py_type'] == 'int'  # col1
        assert result[1]['py_type'] == 'NoneType'  # col2 (no values found)