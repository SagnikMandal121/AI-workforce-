from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from redis import Redis
from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.core.exceptions import AuthenticationError, AuthorizationError
from backend.core.security import Role, TokenType, decode_token, is_role_allowed
from backend.database.session import get_redis_client, get_session
from backend.services.knowledge_service import KnowledgeService
from backend.database.models.user import User
from backend.database.repositories.user import UserRepository
from backend.services.integration_service import IntegrationService
from backend.services.auth_service import AuthService
from backend.services.notification_service import NotificationService
from backend.services.organization_service import OrganizationService
from backend.services.token_service import TokenService
from backend.services.runtime_service import RuntimeService
from backend.services.user_service import UserService


def get_settings_dependency() -> Settings:
    return get_settings()


def get_db() -> Generator[Session, None, None]:
    yield from get_session()


def get_redis() -> Redis:
    return get_redis_client()


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_token_service(
    settings: Settings = Depends(get_settings_dependency),
    redis_client: Redis = Depends(get_redis),
) -> TokenService:
    return TokenService(settings, redis_client)


def get_notification_service() -> NotificationService:
    return NotificationService()


def get_auth_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    token_service: TokenService = Depends(get_token_service),
    notification_service: NotificationService = Depends(get_notification_service),
) -> AuthService:
    return AuthService(
        session=db,
        settings=settings,
        token_service=token_service,
        notification_service=notification_service,
    )


def get_organization_service(db: Session = Depends(get_db)) -> OrganizationService:
    return OrganizationService(db)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def get_integration_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    redis_client: Redis = Depends(get_redis),
) -> IntegrationService:
    return IntegrationService(session=db, settings=settings, redis_client=redis_client)


def get_knowledge_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    redis_client: Redis = Depends(get_redis),
) -> KnowledgeService:
    return KnowledgeService(session=db, settings=settings, redis_client=redis_client)


def get_runtime_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    redis_client: Redis = Depends(get_redis),
) -> RuntimeService:
    return RuntimeService(session=db, settings=settings, redis_client=redis_client)


def get_current_token_payload(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    settings: Settings = Depends(get_settings_dependency),
    token_service: TokenService = Depends(get_token_service),
) -> dict:
    state_payload = getattr(request.state, "current_user_claims", None)
    if state_payload is not None:
        if getattr(request.state, "current_token", None) and token_service.is_access_token_revoked(
            request.state.current_token
        ):
            raise AuthenticationError("Token has been revoked")
        return {
            "raw": getattr(request.state, "current_token", None),
            "sub": UUID(state_payload.sub),
            "organization_id": UUID(state_payload.org_id),
            "email": state_payload.email,
            "role": Role(state_payload.role),
            "jti": state_payload.jti,
            "exp": state_payload.exp,
        }
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token_service.is_access_token_revoked(token):
        raise AuthenticationError("Token has been revoked")
    payload = decode_token(token, settings, expected_type=TokenType.ACCESS)
    return {
        "raw": token,
        "sub": UUID(payload.sub),
        "organization_id": UUID(payload.org_id),
        "email": payload.email,
        "role": Role(payload.role),
        "jti": payload.jti,
        "exp": payload.exp,
    }


def get_current_user(
    payload: dict = Depends(get_current_token_payload),
    repository: UserRepository = Depends(get_user_repository),
) -> User:
    user = repository.get_by_id(payload["sub"], payload["organization_id"])
    if user is None:
        raise AuthenticationError("User not found")
    if user.status.value != "active":
        raise AuthenticationError("User is not active")
    return user


def require_min_role(min_role: Role) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not is_role_allowed(user.role, min_role):
            raise AuthorizationError()
        return user

    return dependency
