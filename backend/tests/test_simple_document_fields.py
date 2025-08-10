"""
Simple test for GET /documents/{id}/fields endpoint to verify it works
"""

import pytest
import requests
from uuid import uuid4

# Use the correct port for testing
BASE_URL = "http://localhost:8001"


def test_document_fields_endpoint_not_found():
    """Test that the endpoint exists and returns 404 for non-existent document"""
    # First create a test user to get a token
    signup_response = requests.post(
        f"{BASE_URL}/auth/signup",
        json={
            "email": f"test_{uuid4()}@example.com",
            "password": "testpass123",
            "business_name": "Test Business"
        }
    )
    assert signup_response.status_code == 200
    
    token = signup_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test the fields endpoint with non-existent document
    non_existent_id = uuid4()
    response = requests.get(
        f"{BASE_URL}/documents/{non_existent_id}/fields",
        headers=headers
    )
    
    # Should return 404
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_document_fields_endpoint_unauthorized():
    """Test that the endpoint requires authentication"""
    non_existent_id = uuid4()
    response = requests.get(f"{BASE_URL}/documents/{non_existent_id}/fields")
    
    # Should return 401 unauthorized
    assert response.status_code == 401


if __name__ == "__main__":
    test_document_fields_endpoint_not_found()
    test_document_fields_endpoint_unauthorized()
    print("✅ All manual tests passed!")