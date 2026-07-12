from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from pydantic import field_validator

from backend.core.security import Role
from database.schemas.organization import OrganizationCreate, OrganizationRead
from database.schemas.token import TokenPair
from database.schemas.user import UserRead


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    logo: str | None = Field(default=None, max_length=1024)
    domain: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=64)
    subscription: str = Field(default="trial", max_length=64)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("company_name", "timezone", "subscription", "first_name", "last_name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=12, max_length=128)


class AcceptInviteRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=12, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class AuthenticatedSession(BaseModel):
    user: UserRead
    organization: OrganizationRead
    tokens: TokenPair


class RegistrationResponse(BaseModel):
    user: UserRead
    organization: OrganizationRead
    message: str


class AuthMessageResponse(BaseModel):
    message: str


class InviteUserRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: Role = Role.EMPLOYEE

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()
