from __future__ import annotations

import pytest

from backend.core.config import Settings
from backend.core.security import Role, UserStatus
from backend.database.repositories.user import UserRepository
from backend.database.schemas.auth import (
    AcceptInviteRequest,
    ForgotPasswordRequest,
    InviteUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from backend.services.auth_service import AuthService
from backend.services.notification_service import NotificationService
from backend.services.token_service import TokenService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    def get(self, key: str):
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def exists(self, key: str) -> int:
        return 1 if key in self.store else 0


class CaptureNotificationService(NotificationService):
    def __init__(self) -> None:
        self.verification_tokens: list[str] = []
        self.password_reset_tokens: list[str] = []
        self.invite_tokens: list[str] = []

    def send_email_verification(self, email: str, token: str) -> None:
        self.verification_tokens.append(token)

    def send_password_reset(self, email: str, token: str) -> None:
        self.password_reset_tokens.append(token)

    def send_invitation(self, email: str, token: str, role: str) -> None:
        self.invite_tokens.append(token)


def make_settings() -> Settings:
    return Settings(
        environment="test",
        secret_key="test-secret",
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
        email_verification_expire_hours=24,
        password_reset_expire_minutes=30,
    )


def build_service(db_session):
    settings = make_settings()
    redis = FakeRedis()
    token_service = TokenService(settings, redis)  # type: ignore[arg-type]
    notifications = CaptureNotificationService()
    service = AuthService(
        session=db_session,
        settings=settings,
        token_service=token_service,
        notification_service=notifications,
    )
    return service, token_service, notifications


def register_payload() -> RegisterRequest:
    return RegisterRequest(
        company_name="Acme Inc",
        domain="acme.example",
        timezone="UTC",
        subscription="trial",
        first_name="Ada",
        last_name="Lovelace",
        email="owner@acme.example",
        password="super-secure-password",
    )


def test_register_verify_and_login(db_session):
    service, _, notifications = build_service(db_session)
    registration = service.register(register_payload())

    assert registration.user.email == "owner@acme.example"
    assert notifications.verification_tokens

    service.verify_email(VerifyEmailRequest(token=notifications.verification_tokens[0]))
    login = service.login(LoginRequest(email="owner@acme.example", password="super-secure-password"))

    assert login.user.status == UserStatus.ACTIVE
    assert login.tokens.access_token
    assert login.tokens.refresh_token


def test_refresh_and_logout_revokes_refresh_token(db_session):
    service, _, notifications = build_service(db_session)
    service.register(register_payload())
    service.verify_email(VerifyEmailRequest(token=notifications.verification_tokens[0]))
    login = service.login(LoginRequest(email="owner@acme.example", password="super-secure-password"))

    refreshed = service.refresh(RefreshRequest(refresh_token=login.tokens.refresh_token))
    assert refreshed.access_token

    service.logout(LogoutRequest(refresh_token=login.tokens.refresh_token), access_token=login.tokens.access_token)
    with pytest.raises(Exception):
        service.refresh(RefreshRequest(refresh_token=login.tokens.refresh_token))


def test_forgot_password_and_reset(db_session):
    service, _, notifications = build_service(db_session)
    service.register(register_payload())
    service.verify_email(VerifyEmailRequest(token=notifications.verification_tokens[0]))

    service.forgot_password(ForgotPasswordRequest(email="owner@acme.example"))
    assert notifications.password_reset_tokens

    service.reset_password(
        ResetPasswordRequest(
            token=notifications.password_reset_tokens[0],
            new_password="even-more-secure-password",
        )
    )
    login = service.login(LoginRequest(email="owner@acme.example", password="even-more-secure-password"))
    assert login.tokens.access_token


def test_invite_and_accept_invite(db_session):
    service, _, notifications = build_service(db_session)
    service.register(register_payload())
    service.verify_email(VerifyEmailRequest(token=notifications.verification_tokens[0]))
    owner_user = UserRepository(db_session).get_by_email("owner@acme.example")
    assert owner_user is not None

    invite_token = service.invite_user(
        inviter=owner_user,
        payload=InviteUserRequest(
            email="admin@acme.example",
            first_name="Grace",
            last_name="Hopper",
            role=Role.ADMIN,
        ),
    )
    assert notifications.invite_tokens

    service.accept_invite(
        AcceptInviteRequest(token=invite_token, new_password="admin-super-secure-password")
    )
    login = service.login(LoginRequest(email="admin@acme.example", password="admin-super-secure-password"))
    assert login.user.role == Role.ADMIN
