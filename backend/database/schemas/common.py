from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampedSchema(ORMBaseModel):
    created_at: datetime
    updated_at: datetime | None = None


class UUIDSchema(ORMBaseModel):
    organization_id: UUID | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


class EmailMixin(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)
