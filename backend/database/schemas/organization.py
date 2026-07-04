from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.database.schemas.common import ORMBaseModel, TimestampedSchema


class OrganizationBase(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    logo: str | None = Field(default=None, max_length=1024)
    domain: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=64)
    subscription: str = Field(default="trial", max_length=64)

    @field_validator("company_name", "timezone", "subscription")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationRead(OrganizationBase, TimestampedSchema):
    organization_id: UUID


class OrganizationUpdate(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    logo: str | None = Field(default=None, max_length=1024)
    domain: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    subscription: str | None = Field(default=None, max_length=64)

    @field_validator("company_name", "timezone", "subscription")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None
