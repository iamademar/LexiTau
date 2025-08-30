from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from .. import models
from ..auth import (
    authenticate_user as auth_authenticate_user,
    create_user_and_business as auth_create_user_and_business,
    create_access_token as auth_create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from ..schemas import SignupRequest, LoginRequest, SignupResponse, LoginResponse, UserResponse, BusinessResponse


class AuthService:
    """Service for handling authentication business logic."""
    
    @staticmethod
    def check_user_exists(db: Session, email: str) -> bool:
        """Check if a user with the given email already exists."""
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        return existing_user is not None
    
    @staticmethod
    def create_access_token_for_user(user: models.User) -> str:
        """Create an access token for the given user."""
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        return auth_create_access_token(
            data={"sub": user.email, "user_id": user.id, "business_id": user.business_id},
            expires_delta=access_token_expires
        )
    
    @staticmethod
    def signup_user(db: Session, request: SignupRequest) -> SignupResponse:
        """
        Create a new user and business account.
        
        Args:
            db: Database session
            request: Signup request data
            
        Returns:
            SignupResponse with user, business, and access token
            
        Raises:
            HTTPException: If email already exists or creation fails
        """
        try:
            # Check if user already exists
            if AuthService.check_user_exists(db, request.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Create user and business
            user = auth_create_user_and_business(
                db=db,
                email=request.email,
                password=request.password,
                business_name=request.business_name
            )
            
            # Create access token
            access_token = AuthService.create_access_token_for_user(user)
            
            return SignupResponse(
                user=UserResponse.model_validate(user),
                business=BusinessResponse.model_validate(user.business),
                access_token=access_token,
                token_type="bearer"
            )
            
        except HTTPException:
            db.rollback()
            raise
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create account"
            )
    
    @staticmethod
    def login_user(db: Session, request: LoginRequest) -> LoginResponse:
        """
        Authenticate user and return login response.
        
        Args:
            db: Database session
            request: Login request data
            
        Returns:
            LoginResponse with user and access token
            
        Raises:
            HTTPException: If authentication fails
        """
        user = auth_authenticate_user(db, request.email, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = AuthService.create_access_token_for_user(user)
        
        return LoginResponse(
            user=UserResponse.model_validate(user),
            access_token=access_token,
            token_type="bearer"
        )