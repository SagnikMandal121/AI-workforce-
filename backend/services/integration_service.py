from __future__ import annotations

import jwt
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.config import Settings
from backend.core.exceptions import ConflictError, NotFoundError, ValidationError
from backend.core.integration_crypto import CredentialCipher
from backend.core.security import utcnow
from backend.database.models.integration import (
    Integration,
    IntegrationLog,
    IntegrationPermission,
    IntegrationProvider,
    IntegrationStatus,
    OAuthToken,
)
from backend.database.models.user import User
from backend.database.repositories.integration import (
    IntegrationLogRepository,
    IntegrationPermissionRepository,
    IntegrationRepository,
    OAuthTokenRepository,
)
from backend.database.schemas.integration import (
    IntegrationActionRequest,
    IntegrationCallbackRequest,
    IntegrationConnectRequest,
    IntegrationConnectResponse,
    IntegrationHubResponse,
    IntegrationRead,
    IntegrationStatusResponse,
    IntegrationTestResponse,
    SupportedIntegrationRead,
)
from backend.services.integrations.providers import IntegrationRegistry, ProviderAuthResult


@dataclass(frozen=True)
class OAuthStatePayload:
    provider: str
    integration_id: str
    organization_id: str
    user_id: str
    nonce: str
    exp: int
    iat: int


class IntegrationService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        redis_client: Redis | None = None,
        registry: IntegrationRegistry | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.redis = redis_client
        self.registry = registry or IntegrationRegistry()
        self.cipher = CredentialCipher(settings.integration_encryption_key)
        self.integrations = IntegrationRepository(session)
        self.tokens = OAuthTokenRepository(session)
        self.permissions = IntegrationPermissionRepository(session)
        self.logs = IntegrationLogRepository(session)

    def list_hub(self, current_user: User) -> IntegrationHubResponse:
        integrations = self._list_visible_integrations(current_user)
        return IntegrationHubResponse(
            supported_integrations=[SupportedIntegrationRead.model_validate(item) for item in self.registry.list_supported()],
            integrations=[self._serialize_integration(integration) for integration in integrations],
        )

    def get_status(self, current_user: User) -> IntegrationStatusResponse:
        integrations = self._list_visible_integrations(current_user)
        return IntegrationStatusResponse(
            supported_integrations=[SupportedIntegrationRead.model_validate(item) for item in self.registry.list_supported()],
            integrations=[self._serialize_integration(integration) for integration in integrations],
            total_integrations=len(integrations),
            connected_integrations=sum(1 for item in integrations if item.status == IntegrationStatus.CONNECTED),
            pending_integrations=sum(1 for item in integrations if item.status == IntegrationStatus.PENDING),
            disconnected_integrations=sum(1 for item in integrations if item.status == IntegrationStatus.DISCONNECTED),
            expired_integrations=sum(1 for item in integrations if item.status == IntegrationStatus.EXPIRED),
            healthy_integrations=sum(
                1 for item in integrations if item.status == IntegrationStatus.CONNECTED and item.last_error is None
            ),
        )

    def connect(self, current_user: User, payload: IntegrationConnectRequest) -> IntegrationConnectResponse:
        provider = self.registry.get(payload.provider)
        existing = self.integrations.get_by_provider(current_user.organization_id, payload.provider)
        if existing is not None and existing.status != IntegrationStatus.DISCONNECTED:
            raise ConflictError(f"{payload.provider.value} is already connected for this organization")

        integration = existing or Integration(
            organization_id=current_user.organization_id,
            provider=payload.provider,
            display_name=payload.label or provider.display_name,
            status=IntegrationStatus.PENDING,
            metadata_json={},
        )
        integration.display_name = payload.label or provider.display_name
        integration.status = IntegrationStatus.PENDING
        integration.metadata_json = {
            **payload.metadata,
            "requested_scopes": payload.scopes,
            "provider": payload.provider.value,
        }
        integration.last_error = None
        integration.disconnected_at = None

        if existing is None:
            self.integrations.create(integration)

        self._replace_permissions(integration, current_user, payload.allowed_user_ids)
        self._log(
            integration=integration,
            actor_user=current_user,
            action="connect",
            message="Connection initialized",
            payload={"provider": payload.provider.value},
        )

        state = self._create_oauth_state(current_user, integration)
        auth_result = provider.connect(integration=integration, state=state, scopes=payload.scopes)

        if payload.authorization_code:
            integration_read = self.authenticate(
                current_user=current_user,
                provider=payload.provider,
                callback=IntegrationCallbackRequest(
                    code=payload.authorization_code,
                    state=state,
                    redirect_uri=payload.redirect_uri,
                ),
                integration=integration,
            )
            return IntegrationConnectResponse(
                integration=integration_read,
                authorization_url=None,
                state=None,
                requires_authorization=False,
                message="Integration connected successfully",
            )

        self.session.commit()
        return IntegrationConnectResponse(
            integration=self._serialize_integration(integration),
            authorization_url=auth_result.authorization_url,
            state=auth_result.state,
            requires_authorization=True,
            message="Authorization required to complete the connection",
        )

    def authenticate(
        self,
        *,
        current_user: User | None,
        provider: IntegrationProvider,
        callback: IntegrationCallbackRequest,
        integration: Integration | None = None,
    ) -> IntegrationRead:
        state_payload = self._decode_oauth_state(callback.state)
        if state_payload.provider != provider.value:
            raise ValidationError("OAuth state does not match the requested provider")

        target_integration = integration or self.integrations.get_by_id(UUID(state_payload.integration_id))
        if target_integration is None:
            raise NotFoundError("Integration not found")
        if target_integration.organization_id != UUID(state_payload.organization_id):
            raise ValidationError("OAuth state does not match the organization")

        provider_impl = self.registry.get(provider)
        auth_result = provider_impl.authenticate(
            integration=target_integration,
            authorization_code=callback.code,
            redirect_uri=callback.redirect_uri,
            scopes=target_integration.metadata_json.get("requested_scopes", []),
        )

        self._persist_tokens(target_integration, auth_result)
        target_integration.external_account_id = auth_result.external_account_id
        target_integration.status = IntegrationStatus.CONNECTED
        target_integration.last_connected_at = utcnow()
        target_integration.last_validated_at = utcnow()
        target_integration.last_error = None
        self._log(
            integration=target_integration,
            actor_user=current_user,
            action="authenticate",
            message="OAuth authentication completed",
            payload={"provider": provider.value, "state": callback.state},
        )
        self.session.commit()
        return self._serialize_integration(target_integration)

    def callback(self, current_user: User | None, provider: IntegrationProvider, payload: IntegrationCallbackRequest) -> IntegrationRead:
        return self.authenticate(current_user=current_user, provider=provider, callback=payload)

    def validate(self, current_user: User, integration_id: UUID) -> IntegrationTestResponse:
        integration = self._get_accessible_integration(current_user, integration_id)
        token = self._require_token(integration)
        provider = self.registry.get(integration.provider)
        validation = provider.validate(integration=integration)
        integration.last_validated_at = utcnow()
        integration.last_error = None if validation.valid else validation.message
        integration.status = IntegrationStatus.CONNECTED if validation.valid else IntegrationStatus.VALIDATION_FAILED
        self._log(
            integration=integration,
            actor_user=current_user,
            action="validate",
            message=validation.message,
            success=validation.valid,
            status="ok" if validation.valid else "failed",
            payload={"checked_at": validation.metadata.get("checked_at"), "provider": integration.provider.value},
        )
        self.session.commit()
        return IntegrationTestResponse(
            integration=self._serialize_integration(integration),
            action="validate",
            result={"valid": validation.valid, "message": validation.message, "metadata": validation.metadata},
            valid=validation.valid,
            message=validation.message,
        )

    def test(self, current_user: User, payload: IntegrationActionRequest) -> IntegrationTestResponse:
        integration = self._get_accessible_integration(current_user, payload.integration_id)
        self._require_token(integration)
        provider = self.registry.get(integration.provider)
        result = provider.execute_action(integration=integration, action=payload.action, payload=payload.payload)
        self._log(
            integration=integration,
            actor_user=current_user,
            action=payload.action,
            message=result.message,
            success=result.success,
            status="ok" if result.success else "failed",
            payload=result.payload,
        )
        self.session.commit()
        return IntegrationTestResponse(
            integration=self._serialize_integration(integration),
            action=payload.action,
            result=result.payload,
            valid=result.success,
            message=result.message,
        )

    def disconnect(self, current_user: User, integration_id: UUID) -> IntegrationRead:
        integration = self._get_accessible_integration(current_user, integration_id)
        provider = self.registry.get(integration.provider)
        disconnect_result = provider.disconnect(integration=integration)
        token = self.tokens.get_by_integration_id(integration.id)
        if token is not None:
            token.revoked_at = utcnow()
        integration.status = IntegrationStatus.DISCONNECTED
        integration.disconnected_at = utcnow()
        integration.last_error = None
        self._log(
            integration=integration,
            actor_user=current_user,
            action="disconnect",
            message=disconnect_result.message,
            success=disconnect_result.success,
            status="ok" if disconnect_result.success else "failed",
            payload={"provider": integration.provider.value},
        )
        self.session.commit()
        return self._serialize_integration(integration)

    def refresh_due_tokens(self, limit: int = 100) -> int:
        cutoff = utcnow() + timedelta(minutes=self.settings.integration_refresh_window_minutes)
        due_tokens = self.tokens.list_due_for_refresh(cutoff)[:limit]
        refreshed = 0
        for token in due_tokens:
            integration = token.integration
            if integration is None:
                continue
            if not self._acquire_refresh_lock(integration.id):
                continue
            try:
                provider = self.registry.get(integration.provider)
                refresh_result = provider.refresh_token(
                    integration=integration,
                    refresh_token=self.cipher.decrypt(token.refresh_token_encrypted) if token.refresh_token_encrypted else "",
                    scopes=token.scopes,
                )
                self._persist_refreshed_tokens(token, refresh_result)
                integration.status = IntegrationStatus.CONNECTED
                integration.last_error = None
                self._log(
                    integration=integration,
                    actor_user=None,
                    action="refresh_token",
                    message="Token refresh completed",
                    payload=refresh_result.metadata,
                )
                refreshed += 1
            except Exception as exc:  # pragma: no cover - defensive refresh guard
                token.refresh_attempts += 1
                token.last_refresh_error = str(exc)
                integration.status = IntegrationStatus.EXPIRED
                integration.last_error = str(exc)
                self._log(
                    integration=integration,
                    actor_user=None,
                    action="refresh_token",
                    message="Token refresh failed",
                    success=False,
                    status="failed",
                    payload={"error": str(exc)},
                    error_details={"error": str(exc)},
                    attempt_number=token.refresh_attempts,
                )
            finally:
                self.session.commit()
        return refreshed

    def _serialize_integration(self, integration: Integration) -> IntegrationRead:
        permissions = [
            {
                "id": permission.id,
                "integration_id": permission.integration_id,
                "user_id": permission.user_id,
                "can_access": permission.can_access,
                "can_configure": permission.can_configure,
                "granted_by_user_id": permission.granted_by_user_id,
                "created_at": permission.created_at,
                "updated_at": permission.updated_at,
            }
            for permission in integration.permissions
        ]
        logs = [
            {
                "id": log.id,
                "integration_id": log.integration_id,
                "organization_id": log.organization_id,
                "actor_user_id": log.actor_user_id,
                "action": log.action,
                "success": log.success,
                "status": log.status,
                "message": log.message,
                "attempt_number": log.attempt_number,
                "request_id": log.request_id,
                "payload": log.payload,
                "error_details": log.error_details,
                "created_at": log.created_at,
                "updated_at": log.updated_at,
            }
            for log in list(integration.logs)[0:20]
        ]
        return IntegrationRead(
            id=integration.id,
            organization_id=integration.organization_id,
            provider=integration.provider,
            display_name=integration.display_name,
            status=integration.status,
            external_account_id=integration.external_account_id,
            metadata_json=integration.metadata_json,
            last_connected_at=integration.last_connected_at,
            last_validated_at=integration.last_validated_at,
            last_error=integration.last_error,
            disconnected_at=integration.disconnected_at,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
            has_tokens=integration.oauth_token is not None,
            permissions=permissions,
            logs=logs,
        )

    def _list_visible_integrations(self, current_user: User) -> list[Integration]:
        if current_user.role.value in {"Owner", "Admin"}:
            stmt = (
                select(Integration)
                .where(Integration.organization_id == current_user.organization_id)
                .options(selectinload(Integration.oauth_token), selectinload(Integration.permissions), selectinload(Integration.logs))
                .order_by(Integration.created_at.desc())
            )
            return list(self.session.execute(stmt).scalars().all())

        permissions = self.permissions.list_accessible_for_user(current_user.organization_id, current_user.id)
        return [permission.integration for permission in permissions if permission.integration is not None]

    def _get_accessible_integration(self, current_user: User, integration_id: UUID) -> Integration:
        integration = self.integrations.get_by_id(integration_id)
        if integration is None or integration.organization_id != current_user.organization_id:
            raise NotFoundError("Integration not found")
        if current_user.role.value not in {"Owner", "Admin"}:
            permission = next(
                (item for item in integration.permissions if item.user_id == current_user.id and item.can_access),
                None,
            )
            if permission is None:
                raise ValidationError("You do not have access to this integration")
        return integration

    def _replace_permissions(self, integration: Integration, current_user: User, allowed_user_ids: list[UUID]) -> None:
        self.permissions.revoke_for_integration(integration.id)
        recipients = {current_user.id, *allowed_user_ids}
        for user_id in recipients:
            self.permissions.grant(
                IntegrationPermission(
                    integration_id=integration.id,
                    user_id=user_id,
                    can_access=True,
                    can_configure=user_id == current_user.id,
                    granted_by_user_id=current_user.id,
                )
            )

    def _log(
        self,
        *,
        integration: Integration,
        actor_user: User | None,
        action: str,
        message: str,
        success: bool = True,
        status: str = "ok",
        payload: dict[str, object] | None = None,
        error_details: dict[str, object] | None = None,
        attempt_number: int = 1,
    ) -> IntegrationLog:
        return self.logs.create(
            IntegrationLog(
                integration_id=integration.id,
                organization_id=integration.organization_id,
                actor_user_id=actor_user.id if actor_user else None,
                action=action,
                success=success,
                status=status,
                message=message,
                attempt_number=attempt_number,
                request_id=uuid4().hex,
                payload=payload or {},
                error_details=error_details or {},
            )
        )

    def _persist_tokens(self, integration: Integration, auth_result: ProviderAuthResult) -> OAuthToken:
        token = OAuthToken(
            integration_id=integration.id,
            access_token_encrypted=self.cipher.encrypt(auth_result.access_token),
            refresh_token_encrypted=self.cipher.encrypt(auth_result.refresh_token) if auth_result.refresh_token else None,
            token_type="oauth2",
            scopes=auth_result.scopes,
            access_token_expires_at=auth_result.access_token_expires_at,
            refresh_token_expires_at=auth_result.refresh_token_expires_at,
            refresh_attempts=0,
            last_refreshed_at=utcnow(),
            last_refresh_error=None,
            revoked_at=None,
        )
        stored = self.tokens.upsert(token)
        integration.oauth_token = stored
        integration.metadata_json = {
            **integration.metadata_json,
            **auth_result.metadata,
            "scopes": auth_result.scopes,
        }
        return stored

    def _persist_refreshed_tokens(self, token: OAuthToken, refresh_result: ProviderAuthResult) -> None:
        token.access_token_encrypted = self.cipher.encrypt(refresh_result.access_token)
        token.refresh_token_encrypted = (
            self.cipher.encrypt(refresh_result.refresh_token) if refresh_result.refresh_token else None
        )
        token.access_token_expires_at = refresh_result.access_token_expires_at
        token.refresh_token_expires_at = refresh_result.refresh_token_expires_at
        token.last_refreshed_at = utcnow()
        token.last_refresh_error = None
        token.refresh_attempts = 0
        token.integration.oauth_token = token

    def _create_oauth_state(self, current_user: User, integration: Integration) -> str:
        now = utcnow()
        payload = {
            "provider": integration.provider.value,
            "integration_id": str(integration.id),
            "organization_id": str(current_user.organization_id),
            "user_id": str(current_user.id),
            "nonce": uuid4().hex,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self.settings.integration_oauth_state_expire_minutes)).timestamp()),
        }
        return jwt.encode(payload, self.settings.secret_key, algorithm=self.settings.jwt_algorithm)

    def _decode_oauth_state(self, state: str) -> OAuthStatePayload:
        try:
            payload = jwt.decode(state, self.settings.secret_key, algorithms=[self.settings.jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise ValidationError("Invalid OAuth state") from exc
        return OAuthStatePayload(**payload)

    def _require_token(self, integration: Integration) -> OAuthToken:
        token = self.tokens.get_by_integration_id(integration.id)
        if token is None or token.revoked_at is not None:
            raise NotFoundError("Integration credentials were not found")
        return token

    def _acquire_refresh_lock(self, integration_id: UUID) -> bool:
        if self.redis is None:
            return True
        try:
            return bool(
                self.redis.set(
                    f"integration:refresh-lock:{integration_id}",
                    "1",
                    ex=self.settings.integration_refresh_lock_seconds,
                    nx=True,
                )
            )
        except TypeError:
            return True