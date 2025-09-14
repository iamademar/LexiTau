"""Unit tests for application settings."""
import os
import pytest
from unittest.mock import patch

from app.core.settings import Settings, get_settings


class TestSettings:
    """Test settings defaults and environment variable overrides."""

    def test_vanna_defaults(self):
        """Test that Vanna AI settings have correct defaults."""
        settings = Settings()

        # Required fields with defaults
        assert settings.vanna_model == "my_model"
        assert settings.vanna_api_key == ""

        # Allow-list defaults
        assert settings.vanna_allowed_schemas == ["public"]
        assert settings.vanna_allowed_tables == [
            "public.documents", "public.line_items", "public.extracted_fields",
            "public.clients", "public.projects", "public.categories",
        ]

        # Tenant scope defaults
        assert settings.vanna_tenant_column == "business_id"
        assert settings.vanna_tenant_param == "business_id"

        # Timeout and row limit defaults
        assert settings.vanna_default_timeout_s == 5
        assert settings.vanna_default_row_limit == 500
        assert settings.vanna_work_mem is None

        # SELECT * expansion defaults
        assert settings.vanna_expand_select_star is True
        assert settings.vanna_expand_exclude_types == ["bytea"]
        assert settings.vanna_expand_exclude_name_patterns == ["password", "secret", "api[_-]?key", "token"]

        # Per-table excludes default
        expected_excludes = [
            "public.users.password_hash",
            "public.documents.file_url",
            "public.users.email",
            "public.extracted_fields.value",
            "public.field_corrections.original_value",
            "public.field_corrections.corrected_value",
            "public.line_items.description",
        ]
        assert settings.vanna_expand_exclude_columns == expected_excludes

        # Tenant enforcement defaults
        assert settings.vanna_tenant_enforce_per_table is True
        assert settings.vanna_tenant_required_tables == [
            "public.documents", "public.line_items", "public.extracted_fields",
            "public.clients", "public.projects", "public.categories",
        ]

        # Function deny-list defaults (check a few key patterns)
        assert r"^pg_sleep(?:_for|_until)?$" in settings.vanna_function_denylist
        assert r"^dblink.*$" in settings.vanna_function_denylist
        assert r"^set_config$" in settings.vanna_function_denylist

        # Auditing defaults
        assert settings.vanna_audit_enabled is True
        assert settings.vanna_audit_redact is False
        assert settings.vanna_always_200_on_errors is False

    def test_environment_default(self):
        """Test that environment field has correct default."""
        settings = Settings()
        assert settings.environment == "development"

    @patch.dict(os.environ, {
        "VANNA_MODEL": "test_model",
        "VANNA_API_KEY": "test_key_123",
        "ENVIRONMENT": "prod"
    })
    def test_env_overrides_basic_fields(self):
        """Test that environment variables override basic Vanna settings."""
        settings = Settings()
        assert settings.vanna_model == "test_model"
        assert settings.vanna_api_key == "test_key_123"
        assert settings.environment == "prod"

    @patch.dict(os.environ, {
        "VANNA_ALLOWED_SCHEMAS": '["custom", "schema2"]',
        "VANNA_ALLOWED_TABLES": '["custom.table1", "custom.table2"]',
    })
    def test_env_overrides_list_fields(self):
        """Test that environment variables override list-based settings."""
        settings = Settings()
        assert settings.vanna_allowed_schemas == ["custom", "schema2"]
        assert settings.vanna_allowed_tables == ["custom.table1", "custom.table2"]

    @patch.dict(os.environ, {
        "VANNA_DEFAULT_TIMEOUT_S": "10",
        "VANNA_DEFAULT_ROW_LIMIT": "1000",
        "VANNA_WORK_MEM": "128MB"
    })
    def test_env_overrides_numeric_fields(self):
        """Test that environment variables override numeric settings."""
        settings = Settings()
        assert settings.vanna_default_timeout_s == 10
        assert settings.vanna_default_row_limit == 1000
        assert settings.vanna_work_mem == "128MB"

    @patch.dict(os.environ, {
        "VANNA_EXPAND_SELECT_STAR": "false",
        "VANNA_TENANT_ENFORCE_PER_TABLE": "false",
        "VANNA_AUDIT_ENABLED": "false"
    })
    def test_env_overrides_boolean_fields(self):
        """Test that environment variables override boolean settings."""
        settings = Settings()
        assert settings.vanna_expand_select_star is False
        assert settings.vanna_tenant_enforce_per_table is False
        assert settings.vanna_audit_enabled is False

    @patch.dict(os.environ, {
        "VANNA_EXPAND_EXCLUDE_COLUMNS": '["table1.col1", "table2.col2"]'
    })
    def test_env_overrides_complex_list(self):
        """Test environment override for complex list fields."""
        settings = Settings()
        assert settings.vanna_expand_exclude_columns == ["table1.col1", "table2.col2"]

    @patch.dict(os.environ, {
        "VANNA_FUNCTION_DENYLIST": '["^test_func$", "^another_func.*$"]'
    })
    def test_env_overrides_function_denylist(self):
        """Test environment override for function deny-list."""
        settings = Settings()
        assert settings.vanna_function_denylist == ["^test_func$", "^another_func.*$"]

    def test_get_settings_function(self):
        """Test the get_settings function returns Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

        # Verify it has Vanna settings
        assert hasattr(settings, 'vanna_model')
        assert hasattr(settings, 'vanna_api_key')
        assert hasattr(settings, 'environment')