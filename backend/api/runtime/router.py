from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from backend.core.deps import get_current_user, get_runtime_service, require_min_role
from backend.core.security import Role
from backend.database.schemas.runtime import (
    RuntimeAgentCreate,
    RuntimeAgentRead,
    RuntimeApprovalCreate,
    RuntimeApprovalRead,
    RuntimeConversationRead,
    RuntimeEventRead,
    RuntimePlanRead,
    RuntimeStatusResponse,
    RuntimeTaskCreate,
    RuntimeTaskExecutionRequest,
    RuntimeTaskExecutionResponse,
    RuntimeTaskRead,
    RuntimeTelemetryRead,
)
from backend.services.runtime_service import RuntimeService

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/status", response_model=RuntimeStatusResponse)
def get_status(current_user=Depends(get_current_user), runtime_service: RuntimeService = Depends(get_runtime_service)):
    return runtime_service.get_status(current_user.organization_id)


@router.get("/agents", response_model=list[RuntimeAgentRead])
def list_agents(current_user=Depends(get_current_user), runtime_service: RuntimeService = Depends(get_runtime_service)):
    return runtime_service.list_agents(current_user.organization_id)


@router.post("/agents", response_model=RuntimeAgentRead)
def register_agent(
    payload: RuntimeAgentCreate,
    current_user=Depends(require_min_role(Role.ADMIN)),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    return runtime_service.register_agent(current_user.organization_id, payload)


@router.get("/agents/{agent_id}", response_model=RuntimeAgentRead)
def get_agent(
    agent_id: UUID,
    current_user=Depends(get_current_user),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    return runtime_service.get_agent(current_user.organization_id, agent_id)


@router.post("/tasks/plan", response_model=RuntimeTaskExecutionResponse)
def plan_task(
    payload: RuntimeTaskCreate,
    current_user=Depends(get_current_user),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    task, plan = runtime_service.plan_task(organization_id=current_user.organization_id, request=payload, current_user=current_user)
    return RuntimeTaskExecutionResponse(task=task, plan=plan, result={"planned": True})


@router.post("/tasks/execute", response_model=RuntimeTaskExecutionResponse)
async def execute_task(
    payload: RuntimeTaskExecutionRequest,
    current_user=Depends(get_current_user),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    return await runtime_service.execute_task(organization_id=current_user.organization_id, request=payload, current_user=current_user)


@router.get("/tasks", response_model=list[RuntimeTaskRead])
def list_tasks(current_user=Depends(get_current_user), runtime_service: RuntimeService = Depends(get_runtime_service)):
    return runtime_service.list_tasks(current_user.organization_id)


@router.get("/tasks/{task_id}", response_model=RuntimeTaskRead)
def get_task(task_id: UUID, current_user=Depends(get_current_user), runtime_service: RuntimeService = Depends(get_runtime_service)):
    return runtime_service.get_task(current_user.organization_id, task_id)


@router.get("/conversations", response_model=list[RuntimeConversationRead])
def list_conversations(current_user=Depends(get_current_user), runtime_service: RuntimeService = Depends(get_runtime_service)):
    return runtime_service.list_conversations(current_user.organization_id)


@router.get("/conversations/{conversation_id}", response_model=RuntimeConversationRead)
def get_conversation(
    conversation_id: UUID,
    current_user=Depends(get_current_user),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    return runtime_service.get_conversation(current_user.organization_id, conversation_id)


@router.get("/events", response_model=list[RuntimeEventRead])
def list_events(current_user=Depends(get_current_user), runtime_service: RuntimeService = Depends(get_runtime_service)):
    return runtime_service.list_events(current_user.organization_id)


@router.get("/tasks/{task_id}/telemetry", response_model=list[RuntimeTelemetryRead])
def list_telemetry(task_id: UUID, current_user=Depends(get_current_user), runtime_service: RuntimeService = Depends(get_runtime_service)):
    return runtime_service.list_telemetry(current_user.organization_id, task_id)


@router.post("/approvals/approve", response_model=RuntimeApprovalRead)
def approve(
    payload: RuntimeApprovalCreate,
    current_user=Depends(require_min_role(Role.ADMIN)),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    return runtime_service.approve(current_user.organization_id, payload, decided_by=current_user.id)


@router.post("/approvals/reject", response_model=RuntimeApprovalRead)
def reject(
    payload: RuntimeApprovalCreate,
    current_user=Depends(require_min_role(Role.ADMIN)),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    return runtime_service.reject(current_user.organization_id, payload, decided_by=current_user.id)
