from fastapi import APIRouter, Depends

from backend.core.deps import require_min_role
from backend.core.security import Role
from backend.database.schemas.auth import AuthMessageResponse

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", response_model=AuthMessageResponse)
def list_permissions(current_user=Depends(require_min_role(Role.ADMIN))):
    return AuthMessageResponse(message="Permissions scaffold")
