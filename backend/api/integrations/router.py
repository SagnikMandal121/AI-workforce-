from fastapi import APIRouter, Depends
from uuid import UUID

from backend.core.deps import get_current_user, get_integration_service, require_min_role
from backend.core.security import Role
from backend.database.models.integration import IntegrationProvider
from backend.database.schemas.integration import (
    IntegrationActionRequest,
    IntegrationCallbackRequest,
    IntegrationConnectRequest,
    IntegrationConnectResponse,
    IntegrationHubResponse,
    IntegrationMessageResponse,
    IntegrationRead,
    IntegrationStatusResponse,
    IntegrationTestResponse,
)
from backend.services.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=IntegrationHubResponse)
def list_integrations(
    current_user=Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    return integration_service.list_hub(current_user)


@router.get("/status", response_model=IntegrationStatusResponse)
def integration_status(
    current_user=Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    return integration_service.get_status(current_user)


@router.post("/connect", response_model=IntegrationConnectResponse)
def connect_integration(
    payload: IntegrationConnectRequest,
    current_user=Depends(require_min_role(Role.ADMIN)),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    return integration_service.connect(current_user, payload)


@router.post("/test", response_model=IntegrationTestResponse)
def test_integration(
    payload: IntegrationActionRequest,
    current_user=Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    return integration_service.test(current_user, payload)


@router.delete("/{integration_id}", response_model=IntegrationMessageResponse)
def disconnect_integration(
    integration_id: UUID,
    current_user=Depends(require_min_role(Role.ADMIN)),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    integration_service.disconnect(current_user, integration_id=integration_id)
    return IntegrationMessageResponse(message="Integration disconnected successfully")


@router.get("/oauth/{provider}/callback", response_model=IntegrationRead)
def oauth_callback(
    provider: IntegrationProvider,
    code: str,
    state: str,
    redirect_uri: str | None = None,
    integration_service: IntegrationService = Depends(get_integration_service),
):
    callback = IntegrationCallbackRequest(code=code, state=state, redirect_uri=redirect_uri)
    return integration_service.callback(current_user=None, provider=provider, payload=callback)
