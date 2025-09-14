"""Unit tests for Vanna AI service bootstrap."""
import pytest
from unittest.mock import patch, MagicMock

from app.services.vanna_service import get_vanna, VN, guarded_run_sql


class TestVannaBootstrap:
    """Test Vanna AI service initialization and configuration."""

    @patch('app.services.vanna_service.VannaDefault')
    def test_get_vanna_creates_instance(self, mock_vanna_default):
        """Test that get_vanna creates VannaDefault instance with correct settings."""
        mock_instance = MagicMock()
        mock_vanna_default.return_value = mock_instance

        with patch('app.services.vanna_service.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.vanna_model = "test_model"
            mock_settings.vanna_api_key = "test_key"
            mock_settings.vanna_tenant_param = "business_id"
            mock_settings.vanna_default_timeout_s = 10
            mock_settings.vanna_work_mem = "64MB"
            mock_get_settings.return_value = mock_settings

            vn = get_vanna()

            # Verify VannaDefault was called with correct parameters
            mock_vanna_default.assert_called_once_with(
                model="test_model",
                api_key="test_key"
            )

            # Verify run_sql was overridden
            assert hasattr(vn, 'run_sql')
            assert vn == mock_instance

    @patch('app.services.vanna_service.VannaDefault')
    def test_vn_run_sql_requires_tenant_param(self, mock_vanna_default):
        """Test that VN.run_sql raises RuntimeError when tenant param is missing."""
        mock_instance = MagicMock()
        mock_vanna_default.return_value = mock_instance

        with patch('app.services.vanna_service.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.vanna_model = "test_model"
            mock_settings.vanna_api_key = "test_key"
            mock_settings.vanna_tenant_param = "business_id"
            mock_get_settings.return_value = mock_settings

            vn = get_vanna()

            # Test without tenant param - should raise
            with pytest.raises(RuntimeError, match="business_id is required for VN.run_sql"):
                vn.run_sql("SELECT 1", {})

            # Test with wrong param name - should raise
            with pytest.raises(RuntimeError, match="business_id is required for VN.run_sql"):
                vn.run_sql("SELECT 1", {"other_param": "value"})

    @patch('app.services.vanna_service.VannaDefault')
    @patch('app.services.vanna_service.guarded_run_sql')
    def test_vn_run_sql_with_tenant_param(self, mock_guarded_run_sql, mock_vanna_default):
        """Test that VN.run_sql works correctly when tenant param is provided."""
        mock_instance = MagicMock()
        mock_vanna_default.return_value = mock_instance
        mock_guarded_run_sql.return_value = (["col1"], [["val1"]], 1, False, 100, None)

        with patch('app.services.vanna_service.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.vanna_model = "test_model"
            mock_settings.vanna_api_key = "test_key"
            mock_settings.vanna_tenant_param = "business_id"
            mock_settings.vanna_default_timeout_s = 5
            mock_settings.vanna_work_mem = None
            mock_get_settings.return_value = mock_settings

            vn = get_vanna()

            # Test with tenant param - should work
            result = vn.run_sql("SELECT 1", {"business_id": 123})

            # Should return just the rows (second element from guarded_run_sql tuple)
            assert result == [["val1"]]

            # Verify guarded_run_sql was called correctly
            mock_guarded_run_sql.assert_called_once()
            call_args = mock_guarded_run_sql.call_args
            assert call_args[0][1] == "SELECT 1"  # sql
            assert call_args[0][2] == {"business_id": 123}  # params
            assert call_args[1]["timeout_s"] == 5
            assert call_args[1]["work_mem"] is None

    def test_guarded_run_sql_placeholder(self):
        """Test that guarded_run_sql returns expected placeholder values."""
        from app.db import engine

        result = guarded_run_sql(engine, "SELECT 1", {})

        # Should return tuple: (columns, rows, row_count, truncated, execution_ms, description)
        assert result == ([], [], 0, False, 0, None)

    def test_module_level_vn_instance(self):
        """Test that VN module-level instance is created and is a VannaDefault."""
        from app.services.vanna_service import VN
        from vanna.remote import VannaDefault

        # VN should be an instance of VannaDefault
        assert isinstance(VN, VannaDefault)

        # VN should have the run_sql method overridden
        assert hasattr(VN, 'run_sql')
        assert callable(VN.run_sql)