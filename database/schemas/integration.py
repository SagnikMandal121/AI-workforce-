from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from database.models.integration import IntegrationProvider, IntegrationStatus
from database.schemas.common import TimestampedSchema


class IntegrationPermissionRead(BaseModel):
    id: UUID
    integration_id: UUID
    user_id: UUID
    can_access: bool
    can_configure: bool
    granted_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationLogRead(BaseModel):
    id: UUID
    integration_id: UUID
    organization_id: UUID
    actor_user_id: UUID | None = None
    action: str
    success: bool
    status: str
    message: str
    attempt_number: int
    request_id: str | None = None
    payload: dict[str, Any]
    error_details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SupportedIntegrationRead(BaseModel):
    provider: IntegrationProvider
    display_name: str
    lifecycle: list[str]
    default_scopes: list[str]


class IntegrationRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    provider: IntegrationProvider
    display_name: str
    status: IntegrationStatus
    external_account_id: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    last_connected_at: datetime | None = None
    last_validated_at: datetime | None = None
    last_error: str | None = None
    disconnected_at: datetime | None = None
    has_tokens: bool = False
    permissions: list[IntegrationPermissionRead] = Field(default_factory=list)
    logs: list[IntegrationLogRead] = Field(default_factory=list)


class IntegrationConnectRequest(BaseModel):
    provider: IntegrationProvider
    label: str | None = Field(default=None, max_length=255)
    authorization_code: str | None = Field(default=None, min_length=1, max_length=4096)
    redirect_uri: str | None = Field(default=None, max_length=2048)
    scopes: list[str] = Field(default_factory=list)
    allowed_user_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("scopes")
    @classmethod
    def normalize_scopes(cls, value: list[str]) -> list[str]:
        return [scope.strip() for scope in value if scope and scope.strip()]


class IntegrationCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=4096)
    redirect_uri: str | None = Field(default=None, max_length=2048)


class IntegrationActionRequest(BaseModel):
    integration_id: UUID
    action: str = Field(min_length=1, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def strip_action(cls, value: str) -> str:
        return value.strip().lower()


class IntegrationConnectResponse(BaseModel):
    integration: IntegrationRead
    authorization_url: str | None = None
    state: str | None = None
    requires_authorization: bool
    message: str


class IntegrationTestResponse(BaseModel):
    integration: IntegrationRead
    action: str
    result: dict[str, Any]
    valid: bool
    message: str


class IntegrationStatusResponse(BaseModel):
    supported_integrations: list[SupportedIntegrationRead]
    integrations: list[IntegrationRead]
    total_integrations: int
    connected_integrations: int
    pending_integrations: int
    disconnected_integrations: int
    expired_integrations: int
    healthy_integrations: int


class IntegrationHubResponse(BaseModel):
    supported_integrations: list[SupportedIntegrationRead]
    integrations: list[IntegrationRead]


class IntegrationMessageResponse(BaseModel):
    message: str