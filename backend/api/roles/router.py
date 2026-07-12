from fastapi import APIRouter, Depends

from backend.core.deps import require_min_role
from backend.core.security import Role
from database.schemas.auth import AuthMessageResponse

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=AuthMessageResponse)
def list_roles(current_user=Depends(require_min_role(Role.ADMIN))):
    return AuthMessageResponse(message="Roles scaffold")
