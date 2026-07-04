from fastapi import APIRouter, Depends

from backend.core.deps import require_min_role
from backend.core.security import Role
from backend.database.schemas.auth import AuthMessageResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AuthMessageResponse)
def get_analytics(current_user=Depends(require_min_role(Role.MANAGER))):
    return AuthMessageResponse(message="Analytics scaffold")
