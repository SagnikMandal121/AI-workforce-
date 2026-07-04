from fastapi import APIRouter, Depends

from backend.core.deps import require_min_role
from backend.core.security import Role
from backend.database.schemas.auth import AuthMessageResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=AuthMessageResponse)
def list_conversations(current_user=Depends(require_min_role(Role.EMPLOYEE))):
    return AuthMessageResponse(message="Conversation management scaffold")
