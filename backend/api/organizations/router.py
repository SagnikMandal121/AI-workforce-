from fastapi import APIRouter, Depends

from backend.core.deps import (
    get_auth_service,
    get_current_user,
    get_organization_service,
    require_min_role,
)
from backend.core.security import Role
from backend.database.schemas.auth import AuthMessageResponse, InviteUserRequest
from backend.database.schemas.organization import OrganizationRead, OrganizationUpdate
from backend.services.auth_service import AuthService
from backend.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/me", response_model=OrganizationRead)
def get_my_organization(
    current_user=Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
):
    return service.get_current(current_user.organization_id)


@router.patch("/me", response_model=OrganizationRead)
def update_my_organization(
    payload: OrganizationUpdate,
    current_user=Depends(require_min_role(Role.ADMIN)),
    service: OrganizationService = Depends(get_organization_service),
):
    return service.update_current(current_user.organization_id, payload)


@router.delete("/me", response_model=AuthMessageResponse)
def delete_workspace(
    current_user=Depends(require_min_role(Role.OWNER)),
    service: OrganizationService = Depends(get_organization_service),
):
    service.delete_workspace(current_user.organization_id, current_user.role)
    return AuthMessageResponse(message="Workspace deleted successfully")


@router.post("/invite-admin", response_model=AuthMessageResponse)
def invite_admin(
    payload: InviteUserRequest,
    current_user=Depends(require_min_role(Role.OWNER)),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.invite_user(current_user, payload.model_copy(update={"role": Role.ADMIN}))
    return AuthMessageResponse(message="Admin invitation created successfully")
