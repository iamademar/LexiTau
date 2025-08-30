import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.auth_service import AuthService
from app.schemas import SignupRequest, LoginRequest
from app.models import User, Business


class TestAuthService:
    """Test cases for AuthService business logic."""

    def test_check_user_exists_returns_true_when_user_exists(self):
        """Test that check_user_exists returns True when user exists."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_filter = Mock()
        mock_user = Mock()  # User exists
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_user
        
        # Act
        result = AuthService.check_user_exists(mock_db, "test@example.com")
        
        # Assert
        assert result is True
        mock_db.query.assert_called_once()
    
    def test_check_user_exists_returns_false_when_user_does_not_exist(self):
        """Test that check_user_exists returns False when user does not exist."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_filter = Mock()
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None  # User does not exist
        
        # Act
        result = AuthService.check_user_exists(mock_db, "test@example.com")
        
        # Assert
        assert result is False
    
    def test_create_access_token_for_user(self):
        """Test that create_access_token_for_user creates valid token."""
        # Arrange
        mock_user = Mock()
        mock_user.email = "test@example.com"
        mock_user.id = 1
        mock_user.business_id = 1
        
        with patch('app.services.auth_service.auth_create_access_token') as mock_create_token:
            mock_create_token.return_value = "test_token"
            
            # Act
            result = AuthService.create_access_token_for_user(mock_user)
            
            # Assert
            assert result == "test_token"
            mock_create_token.assert_called_once()
            
            # Check that correct data was passed
            call_args = mock_create_token.call_args
            token_data = call_args[1]['data']
            assert token_data['sub'] == "test@example.com"
            assert token_data['user_id'] == 1
            assert token_data['business_id'] == 1
    
    def test_signup_user_success(self):
        """Test successful user signup."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        mock_user.id = 1
        mock_user.business_id = 1
        mock_user.created_at = datetime.now()
        mock_user.updated_at = datetime.now()
        
        mock_business = Mock()
        mock_business.id = 1
        mock_business.name = "Test Business"  # BusinessResponse expects 'name', not 'business_name'
        mock_business.created_at = datetime.now()
        mock_business.updated_at = datetime.now()
        mock_user.business = mock_business
        
        request = SignupRequest(
            email="test@example.com",
            password="testpassword",
            business_name="Test Business"
        )
        
        with patch.object(AuthService, 'check_user_exists', return_value=False), \
             patch('app.services.auth_service.auth_create_user_and_business', return_value=mock_user), \
             patch.object(AuthService, 'create_access_token_for_user', return_value="test_token"):
            
            # Act
            result = AuthService.signup_user(mock_db, request)
            
            # Assert
            assert result.access_token == "test_token"
            assert result.token_type == "bearer"
    
    def test_signup_user_email_already_exists(self):
        """Test signup fails when email already exists."""
        # Arrange
        mock_db = Mock(spec=Session)
        request = SignupRequest(
            email="test@example.com",
            password="testpassword",
            business_name="Test Business"
        )
        
        with patch.object(AuthService, 'check_user_exists', return_value=True):
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                AuthService.signup_user(mock_db, request)
            
            assert exc_info.value.status_code == 400
            assert "Email already registered" in exc_info.value.detail
            mock_db.rollback.assert_called_once()
    
    def test_signup_user_integrity_error(self):
        """Test signup handles IntegrityError gracefully."""
        # Arrange
        mock_db = Mock(spec=Session)
        request = SignupRequest(
            email="test@example.com",
            password="testpassword",
            business_name="Test Business"
        )
        
        with patch.object(AuthService, 'check_user_exists', return_value=False), \
             patch('app.services.auth_service.auth_create_user_and_business', side_effect=IntegrityError("", "", "")):
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                AuthService.signup_user(mock_db, request)
            
            assert exc_info.value.status_code == 400
            assert "Email already registered" in exc_info.value.detail
            mock_db.rollback.assert_called_once()
    
    def test_login_user_success(self):
        """Test successful user login."""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_user = Mock()
        mock_user.email = "test@example.com"
        mock_user.id = 1
        mock_user.business_id = 1
        mock_user.created_at = datetime.now()
        mock_user.updated_at = datetime.now()
        
        request = LoginRequest(
            email="test@example.com",
            password="testpassword"
        )
        
        with patch('app.services.auth_service.auth_authenticate_user', return_value=mock_user), \
             patch.object(AuthService, 'create_access_token_for_user', return_value="test_token"):
            
            # Act
            result = AuthService.login_user(mock_db, request)
            
            # Assert
            assert result.access_token == "test_token"
            assert result.token_type == "bearer"
    
    def test_login_user_invalid_credentials(self):
        """Test login fails with invalid credentials."""
        # Arrange
        mock_db = Mock(spec=Session)
        request = LoginRequest(
            email="test@example.com",
            password="wrongpassword"
        )
        
        with patch('app.services.auth_service.auth_authenticate_user', return_value=None):
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                AuthService.login_user(mock_db, request)
            
            assert exc_info.value.status_code == 401
            assert "Incorrect email or password" in exc_info.value.detail