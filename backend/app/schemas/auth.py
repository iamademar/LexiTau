from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    business_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    email: str
    business_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

class BusinessResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}

class SignupResponse(BaseModel):
    user: UserResponse
    business: BusinessResponse
    access_token: str
    token_type: str

class LoginResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str