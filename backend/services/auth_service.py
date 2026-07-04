from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.config import Settings
from backend.core.exceptions import AuthenticationError, ConflictError, NotFoundError, TokenError
from backend.core.security import Role, TokenType, UserStatus, hash_password, verify_password, utcnow
from backend.database.models.organization import Organization
from backend.database.models.user import User
from backend.database.repositories.organization import OrganizationRepository
from backend.database.repositories.user import UserRepository
from backend.database.schemas.auth import (
    AuthenticatedSession,
    AcceptInviteRequest,
    ForgotPasswordRequest,
    InviteUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegistrationResponse,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from backend.database.schemas.organization import OrganizationRead
from backend.database.schemas.token import TokenPair
from backend.database.schemas.user import UserRead
from backend.services.notification_service import NotificationService
from backend.services.organization_service import OrganizationService
from backend.services.token_service import TokenService
from backend.services.user_service import UserService


class AuthService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        token_service: TokenService,
        notification_service: NotificationService,
    ) -> None:
        self.session = session
        self.settings = settings
        self.token_service = token_service
        self.notification_service = notification_service
        self.user_repository = UserRepository(session)
        self.organization_repository = OrganizationRepository(session)
        self.user_service = UserService(session)
        self.organization_service = OrganizationService(session)

    def register(self, payload: RegisterRequest) -> RegistrationResponse:
        if self.user_repository.get_by_email(payload.email) is not None:
            raise ConflictError("A user with this email already exists")
        if payload.domain and self.organization_repository.get_by_domain(payload.domain):
            raise ConflictError("An organization with this domain already exists")

        organization = Organization(
            company_name=payload.company_name,
            logo=payload.logo,
            domain=payload.domain,
            timezone=payload.timezone,
            subscription=payload.subscription,
        )
        self.organization_repository.create(organization)

        user = User(
            organization_id=organization.organization_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=Role.OWNER,
            status=UserStatus.PENDING_VERIFICATION,
        )
        self.user_repository.create(user)
        self.session.commit()

        verification_token = self.token_service.issue_one_time_token(
            token_type=TokenType.EMAIL_VERIFICATION,
            user_id=user.id,
            organization_id=organization.organization_id,
            email=user.email,
            role=user.role,
            expires_delta=timedelta(hours=self.settings.email_verification_expire_hours),
        )
        self.notification_service.send_email_verification(user.email, verification_token)

        return RegistrationResponse(
            user=UserRead.model_validate(user),
            organization=OrganizationRead.model_validate(organization),
            message="Registration successful. Please verify your email to continue.",
        )

    def login(self, payload: LoginRequest) -> AuthenticatedSession:
        user = self.user_repository.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise AuthenticationError("Invalid credentials")
        if user.status is not UserStatus.ACTIVE or user.email_verified_at is None:
            raise AuthenticationError("Email address is not verified")

        organization = self.organization_service.get_current(user.organization_id)
        tokens = self._issue_session_tokens(user)
        self.session.commit()
        return AuthenticatedSession(
            user=UserRead.model_validate(user),
            organization=OrganizationRead.model_validate(organization),
            tokens=TokenPair(**tokens),
        )

    def refresh(self, payload: RefreshRequest) -> TokenPair:
        session_payload = self.token_service.get_refresh_session(payload.refresh_token)
        user = self.user_repository.get_by_id(UUID(session_payload.sub), UUID(session_payload.org_id))
        if user is None or user.status is not UserStatus.ACTIVE:
            raise AuthenticationError("User is not active")
        self.token_service.revoke_refresh_token(payload.refresh_token)
        tokens = self._issue_session_tokens(user)
        self.session.commit()
        return TokenPair(**tokens)

    def logout(self, payload: LogoutRequest, access_token: str | None = None) -> None:
        if access_token:
            try:
                self.token_service.revoke_access_token(access_token)
            except TokenError:
                pass
        self.token_service.revoke_refresh_token(payload.refresh_token)
        self.session.commit()

    def forgot_password(self, payload: ForgotPasswordRequest) -> None:
        user = self.user_repository.get_by_email(payload.email)
        if user is None:
            return
        token = self.token_service.issue_one_time_token(
            token_type=TokenType.PASSWORD_RESET,
            user_id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            role=user.role,
            expires_delta=timedelta(minutes=self.settings.password_reset_expire_minutes),
        )
        self.notification_service.send_password_reset(user.email, token)

    def reset_password(self, payload: ResetPasswordRequest) -> None:
        token_payload = self.token_service.consume_one_time_token(
            payload.token, TokenType.PASSWORD_RESET
        )
        user = self.user_repository.get_by_id(UUID(token_payload.sub), UUID(token_payload.org_id))
        if user is None:
            raise NotFoundError("User not found")
        self.user_repository.update_password(user, hash_password(payload.new_password))
        self.session.commit()

    def verify_email(self, payload: VerifyEmailRequest) -> None:
        token_payload = self.token_service.consume_one_time_token(
            payload.token, TokenType.EMAIL_VERIFICATION
        )
        user = self.user_repository.get_by_id(UUID(token_payload.sub), UUID(token_payload.org_id))
        if user is None:
            raise NotFoundError("User not found")
        user.status = UserStatus.ACTIVE
        user.email_verified_at = utcnow()
        self.session.commit()

    def invite_user(self, inviter: User, payload: InviteUserRequest) -> str:
        invited_user = self.user_service.invite_user(
            inviter_role=inviter.role,
            organization_id=inviter.organization_id,
            payload=payload,
        )
        invite_token = self.token_service.issue_one_time_token(
            token_type=TokenType.INVITE,
            user_id=invited_user.id,
            organization_id=invited_user.organization_id,
            email=invited_user.email,
            role=invited_user.role,
            expires_delta=timedelta(days=7),
        )
        self.session.commit()
        self.notification_service.send_invitation(invited_user.email, invite_token, payload.role.value)
        return invite_token

    def accept_invite(self, payload: AcceptInviteRequest) -> None:
        token_payload = self.token_service.consume_one_time_token(payload.token, TokenType.INVITE)
        user = self.user_repository.get_by_id(UUID(token_payload.sub), UUID(token_payload.org_id))
        if user is None:
            raise NotFoundError("User not found")
        if user.status is not UserStatus.INVITED:
            raise AuthenticationError("Invitation is no longer valid")
        self.user_service.activate_invited_user(user=user, new_password=payload.new_password)
        user.email_verified_at = utcnow()
        self.session.commit()

    def _issue_session_tokens(self, user: User) -> dict[str, str]:
        access_token = self.token_service.issue_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            role=user.role,
        )
        refresh_token = self.token_service.issue_refresh_token(
            user_id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            role=user.role,
        )
        self.token_service.store_refresh_session(refresh_token)
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "Bearer"}
