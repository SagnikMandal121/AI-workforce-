from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from database.models.integration import (
    Integration,
    IntegrationLog,
    IntegrationPermission,
    IntegrationProvider,
    IntegrationStatus,
    OAuthToken,
)
from database.repositories.base import BaseRepository


class IntegrationRepository(BaseRepository):
    def get_by_id(self, integration_id: UUID) -> Integration | None:
        stmt = (
            select(Integration)
            .where(Integration.id == integration_id)
            .options(selectinload(Integration.oauth_token), selectinload(Integration.permissions), selectinload(Integration.logs))
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_provider(self, organization_id: UUID, provider: IntegrationProvider) -> Integration | None:
        stmt = (
            select(Integration)
            .where(Integration.organization_id == organization_id, Integration.provider == provider)
            .options(selectinload(Integration.oauth_token), selectinload(Integration.permissions), selectinload(Integration.logs))
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_organization(self, organization_id: UUID) -> list[Integration]:
        stmt = (
            select(Integration)
            .where(Integration.organization_id == organization_id)
            .options(selectinload(Integration.oauth_token), selectinload(Integration.permissions), selectinload(Integration.logs))
            .order_by(Integration.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def create(self, integration: Integration) -> Integration:
        self.session.add(integration)
        self.session.flush()
        return integration

    def delete(self, integration: Integration) -> None:
        self.session.delete(integration)


class OAuthTokenRepository(BaseRepository):
    def get_by_integration_id(self, integration_id: UUID) -> OAuthToken | None:
        stmt = select(OAuthToken).where(OAuthToken.integration_id == integration_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(self, token: OAuthToken) -> OAuthToken:
        existing = self.get_by_integration_id(token.integration_id)
        if existing is None:
            self.session.add(token)
            self.session.flush()
            return token

        existing.access_token_encrypted = token.access_token_encrypted
        existing.refresh_token_encrypted = token.refresh_token_encrypted
        existing.token_type = token.token_type
        existing.scopes = token.scopes
        existing.access_token_expires_at = token.access_token_expires_at
        existing.refresh_token_expires_at = token.refresh_token_expires_at
        existing.refresh_attempts = token.refresh_attempts
        existing.last_refreshed_at = token.last_refreshed_at
        existing.last_refresh_error = token.last_refresh_error
        existing.revoked_at = token.revoked_at
        self.session.flush()
        return existing

    def delete_by_integration_id(self, integration_id: UUID) -> None:
        self.session.execute(delete(OAuthToken).where(OAuthToken.integration_id == integration_id))

    def list_due_for_refresh(self, cutoff: datetime) -> list[OAuthToken]:
        stmt = (
            select(OAuthToken)
            .join(Integration)
            .where(
                OAuthToken.access_token_expires_at <= cutoff,
                OAuthToken.revoked_at.is_(None),
                Integration.status.in_([IntegrationStatus.CONNECTED, IntegrationStatus.EXPIRED]),
            )
            .options(selectinload(OAuthToken.integration))
        )
        return list(self.session.execute(stmt).scalars().all())


class IntegrationPermissionRepository(BaseRepository):
    def list_by_integration(self, integration_id: UUID) -> list[IntegrationPermission]:
        stmt = select(IntegrationPermission).where(IntegrationPermission.integration_id == integration_id)
        return list(self.session.execute(stmt).scalars().all())

    def list_accessible_for_user(self, organization_id: UUID, user_id: UUID) -> list[IntegrationPermission]:
        stmt = (
            select(IntegrationPermission)
            .join(Integration)
            .where(
                Integration.organization_id == organization_id,
                IntegrationPermission.user_id == user_id,
                IntegrationPermission.can_access.is_(True),
            )
            .options(selectinload(IntegrationPermission.integration))
        )
        return list(self.session.execute(stmt).scalars().all())

    def grant(self, permission: IntegrationPermission) -> IntegrationPermission:
        self.session.add(permission)
        self.session.flush()
        return permission

    def revoke_for_integration(self, integration_id: UUID) -> None:
        self.session.execute(delete(IntegrationPermission).where(IntegrationPermission.integration_id == integration_id))


class IntegrationLogRepository(BaseRepository):
    def create(self, log: IntegrationLog) -> IntegrationLog:
        self.session.add(log)
        self.session.flush()
        return log

    def list_by_integration(self, integration_id: UUID, limit: int = 100) -> list[IntegrationLog]:
        stmt = (
            select(IntegrationLog)
            .where(IntegrationLog.integration_id == integration_id)
            .order_by(IntegrationLog.created_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())