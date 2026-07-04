from fastapi import APIRouter, Depends

from backend.core.deps import require_min_role
from backend.core.security import Role
from backend.database.schemas.auth import AuthMessageResponse

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("", response_model=AuthMessageResponse)
def get_billing_dashboard(current_user=Depends(require_min_role(Role.OWNER))):
    return AuthMessageResponse(message="Billing workspace scaffold")
