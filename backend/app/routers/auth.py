from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..dependencies import get_db, get_current_user
from .. import models
from ..schemas import (
    SignupRequest, 
    LoginRequest, 
    SignupResponse, 
    LoginResponse,
    UserResponse
)
from ..services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/signup", response_model=SignupResponse)
async def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    """Create a new user and business account."""
    return AuthService.signup_user(db, request)

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token."""
    return AuthService.login_user(db, request)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: models.User = Depends(get_current_user)
):
    """Get current user information."""
    return UserResponse.model_validate(current_user)