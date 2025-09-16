"""
Tests for schema linking orchestrator service with tenant scoping.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.services.schema_linking_orchestrator_service import (
    _enforce_business_scope,
    _fallback_inject,
    TENANTED_TABLES,
    run_sql_first_linking,
)


class TestBusinessScopeEnforcement:
    """Test the business_id enforcement functions."""

    def test_enforce_business_scope_simple_select(self):
        """Test that business_id constraint is added to a simple SELECT."""
        sql = "SELECT * FROM documents"
        result = _enforce_business_scope(sql, 123)

        # Should add WHERE clause with business_id constraint (SQLGlot uses $ for parameters)
        assert "$business_id" in result
        assert "documents.business_id = $business_id" in result

    def test_enforce_business_scope_with_existing_where(self):
        """Test that business_id constraint is added to existing WHERE clause."""
        sql = "SELECT * FROM documents WHERE name = 'test'"
        result = _enforce_business_scope(sql, 123)

        # Should add AND clause with business_id constraint
        assert "$business_id" in result
        assert "AND" in result
        assert "documents.business_id = $business_id" in result

    def test_enforce_business_scope_with_join(self):
        """Test that business_id constraints are added to JOINed tables."""
        sql = """
        SELECT d.*, ef.*
        FROM documents d
        JOIN extracted_fields ef ON d.id = ef.document_id
        """
        result = _enforce_business_scope(sql, 123)

        # Should add business_id constraints for both tables
        assert "$business_id" in result
        assert "d.business_id = $business_id" in result
        assert "ef.business_id = $business_id" in result

    def test_enforce_business_scope_with_alias(self):
        """Test that aliases are handled correctly."""
        sql = "SELECT * FROM documents AS doc WHERE doc.id = 1"
        result = _enforce_business_scope(sql, 123)

        # Should use alias in the constraint
        assert "doc.business_id = $business_id" in result

    def test_enforce_business_scope_non_tenanted_table(self):
        """Test that non-tenanted tables are not affected."""
        sql = "SELECT * FROM some_other_table"
        result = _enforce_business_scope(sql, 123)

        # Should not add business_id constraint for non-tenanted tables
        assert result == sql

    def test_enforce_business_scope_mixed_tables(self):
        """Test mixed tenanted and non-tenanted tables."""
        sql = """
        SELECT d.*, ot.*
        FROM documents d
        JOIN some_other_table ot ON d.id = ot.ref_id
        """
        result = _enforce_business_scope(sql, 123)

        # Should only add constraint for tenanted table
        assert "d.business_id = $business_id" in result
        assert "ot.business_id" not in result

    def test_fallback_inject_with_where(self):
        """Test fallback injection with existing WHERE clause."""
        sql = "SELECT * FROM documents WHERE name = 'test'"
        result = _fallback_inject(sql)

        assert "AND :business_id IS NOT NULL" in result

    def test_fallback_inject_without_where(self):
        """Test fallback injection without WHERE clause."""
        sql = "SELECT * FROM documents"
        result = _fallback_inject(sql)

        assert "WHERE :business_id IS NOT NULL" in result

    def test_tenanted_tables_constant(self):
        """Test that TENANTED_TABLES includes expected tables."""
        expected_tables = {
            "documents", "extracted_fields", "line_items", "field_corrections",
            "clients", "projects", "categories", "users"
        }

        assert set(TENANTED_TABLES.keys()) == expected_tables
        assert all(col == "business_id" for col in TENANTED_TABLES.values())


class TestOrchestrator:
    """Test the main orchestrator function with tenant scoping."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM client."""
        llm = Mock()
        llm.chat = AsyncMock(return_value="SELECT * FROM documents")
        return llm

    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock embedding service."""
        return Mock()

    @pytest.fixture
    def mock_value_index(self):
        """Create a mock value index."""
        index = Mock()
        index.lookup_literal.return_value = []
        return index

    @pytest.mark.asyncio
    async def test_run_sql_first_linking_requires_business_id(
        self, mock_db, mock_llm, mock_embedding_service, mock_value_index
    ):
        """Test that business_id is required parameter."""
        # Mock the build_five_prompt_variants function
        with pytest.raises(TypeError, match="missing.*required.*business_id"):
            await run_sql_first_linking(
                db=mock_db,
                question="Test question",
                llm=mock_llm,
                embedding_service=mock_embedding_service,
                value_index=mock_value_index,
                # business_id is missing
            )

    @pytest.mark.asyncio
    async def test_run_sql_first_linking_with_business_id(
        self, mock_db, mock_llm, mock_embedding_service, mock_value_index
    ):
        """Test that business_id is passed through and SQL is processed."""
        # Mock the prompt variants building
        mock_variant = Mock()
        mock_variant.messages = [
            {"role": "system", "content": "system"},
            {"role": "assistant", "content": "context"},
            {"role": "user", "content": "question"}
        ]

        mock_five = Mock()
        mock_five.variants = [mock_variant]

        # Mock the build_five_prompt_variants function
        with patch(
            'app.services.schema_linking_orchestrator_service.build_five_prompt_variants',
            return_value=mock_five
        ):
            # Mock the extract_fields_and_literals function
            with patch(
                'app.services.schema_linking_orchestrator_service.extract_fields_and_literals',
                return_value=(set(), [])  # No fields, no literals
            ):
                # Mock the _render_final_context_from_union function
                with patch(
                    'app.services.schema_linking_orchestrator_service._render_final_context_from_union',
                    return_value="context"
                ):
                    result_sql, linked_fields = await run_sql_first_linking(
                        db=mock_db,
                        question="Show me all documents",
                        llm=mock_llm,
                        embedding_service=mock_embedding_service,
                        value_index=mock_value_index,
                        business_id=123,
                    )

                    # Verify the result contains tenant scoping
                    assert "$business_id" in result_sql
                    assert isinstance(linked_fields, set)

                    # Verify LLM was called with tenant hint
                    assert mock_llm.chat.call_count >= 2  # Once per variant + final
                    final_call_args = mock_llm.chat.call_args_list[-1][0][0]
                    assistant_message = next(
                        msg for msg in final_call_args
                        if msg["role"] == "assistant"
                    )
                    assert "TENANT SCOPE" in assistant_message["content"]
                    assert "business_id = 123" in assistant_message["content"]