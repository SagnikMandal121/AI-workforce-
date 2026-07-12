from fastapi import APIRouter, Depends
from uuid import UUID

from backend.core.deps import get_auth_service, get_current_user, get_user_service, require_min_role
from backend.core.security import Role
from database.schemas.auth import AuthMessageResponse, InviteUserRequest
from database.schemas.user import UserRead, UserUpdate
from backend.services.auth_service import AuthService
from backend.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_my_profile(current_user=Depends(get_current_user)):
    return current_user


@router.get("", response_model=list[UserRead])
def list_users(
    current_user=Depends(require_min_role(Role.ADMIN)),
    service: UserService = Depends(get_user_service),
):
    return service.list_by_organization(current_user.organization_id)


@router.get("/{user_id}", response_model=UserRead)
def get_user_by_id(
    user_id: UUID,
    current_user=Depends(require_min_role(Role.ADMIN)),
    service: UserService = Depends(get_user_service),
):
    return service.get_current(user_id, current_user.organization_id)


@router.post("/invite", response_model=AuthMessageResponse)
def invite_user(
    payload: InviteUserRequest,
    current_user=Depends(require_min_role(Role.ADMIN)),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.invite_user(current_user, payload)
    return AuthMessageResponse(message="User invitation created successfully")


@router.patch("/me", response_model=UserRead)
def update_my_profile(
    payload: UserUpdate,
    current_user=Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.update_current(
        current_user,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
