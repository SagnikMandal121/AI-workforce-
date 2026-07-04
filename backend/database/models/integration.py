from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base
from backend.database.models.common import TimeStampedMixin, UUIDMixin


class IntegrationProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    GOOGLE_CALENDAR = "google_calendar"
    WHATSAPP_BUSINESS = "whatsapp_business"
    TWILIO = "twilio"
    SLACK = "slack"
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    GOOGLE_DRIVE = "google_drive"
    NOTION = "notion"


class IntegrationStatus(str, Enum):
    PENDING = "pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"
    ERROR = "error"
    VALIDATION_FAILED = "validation_failed"


class Integration(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_integrations_org_provider"),
        Index("ix_integrations_organization_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        SAEnum(
            IntegrationProvider,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[IntegrationStatus] = mapped_column(
        SAEnum(
            IntegrationStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=IntegrationStatus.PENDING,
        nullable=False,
    )
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    oauth_token = relationship(
        "OAuthToken",
        back_populates="integration",
        uselist=False,
        cascade="all, delete-orphan",
    )
    permissions = relationship(
        "IntegrationPermission",
        back_populates="integration",
        cascade="all, delete-orphan",
    )
    logs = relationship("IntegrationLog", back_populates="integration", cascade="all, delete-orphan")


class OAuthToken(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint("integration_id", name="uq_oauth_tokens_integration"),
        Index("ix_oauth_tokens_expires_at", "access_token_expires_at"),
    )

    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False
    )
    access_token_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    token_type: Mapped[str] = mapped_column(String(64), default="oauth2", nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    integration = relationship("Integration", back_populates="oauth_token")


class IntegrationLog(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "integration_logs"
    __table_args__ = (Index("ix_integration_logs_integration_action", "integration_id", "action"),)

    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False)
    message: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    integration = relationship("Integration", back_populates="logs")


class IntegrationPermission(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "integration_permissions"
    __table_args__ = (
        UniqueConstraint("integration_id", "user_id", name="uq_integration_permissions_user"),
        Index("ix_integration_permissions_user", "user_id"),
    )

    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    can_access: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_configure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    integration = relationship("Integration", back_populates="permissions")