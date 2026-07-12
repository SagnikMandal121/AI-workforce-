from fastapi import APIRouter, Depends, Request

from backend.core.deps import get_auth_service
from database.schemas.auth import (
    AcceptInviteRequest,
    AuthMessageResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RegistrationResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from database.schemas.auth import AuthenticatedSession
from database.schemas.token import TokenPair
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=RegistrationResponse)
def register(payload: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.register(payload)


@router.post("/login", response_model=AuthenticatedSession)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.login(payload)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.refresh(payload)


@router.post("/logout", response_model=AuthMessageResponse)
def logout(
    payload: LogoutRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.logout(payload, access_token=request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or None)
    return AuthMessageResponse(message="Logged out successfully")


@router.post("/forgot-password", response_model=AuthMessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest, auth_service: AuthService = Depends(get_auth_service)
):
    auth_service.forgot_password(payload)
    return AuthMessageResponse(message="If the account exists, password reset instructions were sent")


@router.post("/reset-password", response_model=AuthMessageResponse)
def reset_password(
    payload: ResetPasswordRequest, auth_service: AuthService = Depends(get_auth_service)
):
    auth_service.reset_password(payload)
    return AuthMessageResponse(message="Password reset successfully")


@router.post("/verify-email", response_model=AuthMessageResponse)
def verify_email(payload: VerifyEmailRequest, auth_service: AuthService = Depends(get_auth_service)):
    auth_service.verify_email(payload)
    return AuthMessageResponse(message="Email verified successfully")


@router.post("/accept-invite", response_model=AuthMessageResponse)
def accept_invite(
    payload: AcceptInviteRequest, auth_service: AuthService = Depends(get_auth_service)
):
    auth_service.accept_invite(payload)
    return AuthMessageResponse(message="Invitation accepted successfully")
