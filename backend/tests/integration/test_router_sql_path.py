"""Integration tests for Vanna SQL analysis endpoint."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.models import Business, User
from app.auth import create_access_token, get_password_hash


@pytest.mark.integration
class TestVannaAnalysisEndpoint:
    """Test cases for /vanna/analysis endpoint."""

    @pytest.fixture
    def test_user_and_token(self, db_session):
        """Create a test user and JWT token."""
        # Create business first
        business = Business(name="Test Business")
        db_session.add(business)
        db_session.commit()
        db_session.refresh(business)

        # Create user
        user = User(
            email="testuser@example.com",
            password_hash=get_password_hash("testpassword123"),
            business_id=business.id
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create JWT token
        token_data = {
            "sub": user.email,
            "user_id": user.id,
            "business_id": user.business_id
        }
        token = create_access_token(data=token_data)

        return user, token

    def test_sql_analysis_happy_path(self, client: TestClient, test_user_and_token):
        """Test successful SQL analysis execution."""
        user, token = test_user_and_token

        # Use SQL that queries a real table with proper tenant scoping
        request_data = {
            "sql": "SELECT COUNT(*) as doc_count FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id",
            "trace": False
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert data["ok"] is True
        assert "data" in data
        assert data["error"] is None

        # Check data content
        response_data = data["data"]
        assert response_data["columns"] == ["doc_count"]
        assert len(response_data["rows"]) == 1
        assert response_data["row_count"] == 1
        assert response_data["truncated"] is False
        assert response_data["execution_ms"] >= 0

        # Check the count is a number (could be 0)
        count_value = response_data["rows"][0][0]
        assert isinstance(count_value, int)
        assert count_value >= 0

        # Trace fields should not be present when trace=false
        assert response_data["trace_id"] is None
        assert response_data["guard_flags"] is None
        assert response_data["metadata"] is None
        assert response_data["meta"] is None

    def test_sql_analysis_with_trace(self, client: TestClient, test_user_and_token):
        """Test SQL analysis with trace=true includes metadata."""
        user, token = test_user_and_token

        request_data = {
            "sql": "SELECT COUNT(*) as answer FROM public.documents WHERE business_id = :business_id AND documents.business_id = :business_id",
            "trace": True
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        response_data = data["data"]

        # Trace fields should be present
        assert response_data["trace_id"] is not None
        assert response_data["guard_flags"] is not None
        assert response_data["metadata"] is not None
        assert response_data["meta"] is not None

        # Check column metadata structure
        assert "columns" in response_data["meta"]
        columns_meta = response_data["meta"]["columns"]
        assert len(columns_meta) == 1

        # Check first column metadata
        col1 = columns_meta[0]
        assert col1["name"] == "answer"
        assert col1["py_type"] in ["int", "float"]  # COUNT(*) could return different types
        assert col1["nullable"] is False
        assert col1["serialized_as"] in ["int", "float"]

    def test_client_business_id_override_forbidden(self, client: TestClient, test_user_and_token):
        """Test that client cannot override business_id via query params."""
        user, token = test_user_and_token

        request_data = {
            "sql": "SELECT 1 as test_value",
            "trace": False
        }

        # Attempt to override business_id via query parameter
        response = client.post(
            "/vanna/analysis?business_id=999",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        data = response.json()
        assert "business_id parameter not allowed" in data["detail"]

    def test_guard_error_returns_403(self, client: TestClient, test_user_and_token):
        """Test that guard errors are properly mapped to 403 status."""
        user, token = test_user_and_token

        # Use SQL that should trigger a guard error (missing tenant scope)
        request_data = {
            "sql": "SELECT 1 as test_value",  # No business_id filtering, will trigger missing_tenant_scope
            "trace": False
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data

    def test_both_question_and_sql_provided_422(self, client: TestClient, test_user_and_token):
        """Test validation error when both question and sql are provided."""
        user, token = test_user_and_token

        request_data = {
            "question": "What is the total?",
            "sql": "SELECT 1",
            "trace": False
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_neither_question_nor_sql_provided_422(self, client: TestClient, test_user_and_token):
        """Test validation error when neither question nor sql are provided."""
        user, token = test_user_and_token

        request_data = {
            "trace": False
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_question_path_not_implemented(self, client: TestClient, test_user_and_token):
        """Test that question-based analysis returns not implemented error."""
        user, token = test_user_and_token

        request_data = {
            "question": "What is the total revenue?",
            "trace": False
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 501
        data = response.json()
        assert "not yet implemented" in data["detail"]

    def test_unauthorized_access_401(self, client: TestClient):
        """Test that requests without valid token return 401."""
        request_data = {
            "sql": "SELECT 1",
            "trace": False
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data
            # No Authorization header
        )

        assert response.status_code == 401

    def test_invalid_token_401(self, client: TestClient):
        """Test that requests with invalid token return 401."""
        request_data = {
            "sql": "SELECT 1",
            "trace": False
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401

    def test_malformed_json_400(self, client: TestClient, test_user_and_token):
        """Test that malformed JSON returns 400."""
        user, token = test_user_and_token

        # Send malformed JSON
        response = client.post(
            "/vanna/analysis",
            data='{"sql": "SELECT 1", invalid json',  # Malformed JSON
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 422  # FastAPI returns 422 for JSON decode errors

    def test_sql_with_business_id_parameter_injection(self, client: TestClient, test_user_and_token):
        """Test that business_id parameter is properly injected during SQL execution."""
        user, token = test_user_and_token

        # Use parameterized query that references business_id
        request_data = {
            "sql": "SELECT :business_id as my_business_id WHERE business_id = :business_id",
            "trace": True
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        # business_id parameter should be injected from user context
        assert data["data"]["rows"] == [[user.business_id]]

    def test_large_integer_serialization_integration(self, client: TestClient, test_user_and_token):
        """Test that large integers are properly serialized to strings."""
        user, token = test_user_and_token

        # Use a very large integer beyond JavaScript MAX_SAFE_INTEGER
        large_int = 2**53  # Beyond MAX_SAFE_INTEGER
        request_data = {
            "sql": f"SELECT {large_int} as big_number WHERE business_id = :business_id",
            "trace": True
        }

        response = client.post(
            "/vanna/analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        # Large integer should be serialized as string
        assert data["data"]["rows"] == [[str(large_int)]]

        # Check metadata indicates serialization
        col_meta = data["data"]["meta"]["columns"][0]
        assert col_meta["serialized_as"] == "str"