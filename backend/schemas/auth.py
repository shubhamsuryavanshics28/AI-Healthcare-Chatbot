"""
Pydantic Schemas for Authentication and User Management
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")
    full_name: str = Field(..., min_length=2, max_length=150)
    agree_medical_disclaimer: bool = Field(
        ...,
        description="Patient must acknowledge that this AI assistant provides information and is not a doctor"
    )
    agree_privacy_policy: bool = Field(
        ...,
        description="Patient must agree to the privacy policy"
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consent_type: str
    agreed: bool
    agreed_at: datetime
