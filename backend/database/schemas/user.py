from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.core.security import Role, UserStatus
from backend.database.schemas.common import ORMBaseModel, normalize_email


class UserBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: Role = Role.EMPLOYEE

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return normalize_email(value)


class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=128)
    organization_id: UUID


class UserRead(UserBase, ORMBaseModel):
    id: UUID
    organization_id: UUID
    status: UserStatus
    email_verified_at: datetime | None = None


class UserPublic(UserRead):
    pass


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role: Role | None = None
    status: UserStatus | None = None
