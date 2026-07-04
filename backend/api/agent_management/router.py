from fastapi import APIRouter, Depends

from backend.core.deps import require_min_role
from backend.core.security import Role
from backend.database.schemas.auth import AuthMessageResponse

router = APIRouter(prefix="/agents", tags=["agent-management"])


@router.get("", response_model=AuthMessageResponse)
def list_agents(current_user=Depends(require_min_role(Role.ADMIN))):
    return AuthMessageResponse(message="Agent management scaffold")
