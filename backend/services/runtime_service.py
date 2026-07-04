from __future__ import annotations

from uuid import UUID

from backend.core.config import Settings
from backend.database.repositories.runtime import (
    RuntimeAgentRepository,
    RuntimeApprovalRepository,
    RuntimeConversationMessageRepository,
    RuntimeConversationRepository,
    RuntimeEventRepository,
    RuntimeTelemetryRepository,
    RuntimeTaskRepository,
    RuntimeTaskStepRepository,
)
from backend.database.schemas.knowledge import SearchRequest
from backend.database.schemas.runtime import (
    RuntimeAgentCreate,
    RuntimeAgentRead,
    RuntimeApprovalCreate,
    RuntimeApprovalRead,
    RuntimeConversationRead,
    RuntimePlanRead,
    RuntimeEventRead,
    RuntimeStatusResponse,
    RuntimeTaskCreate,
    RuntimeTaskExecutionRequest,
    RuntimeTaskExecutionResponse,
    RuntimeTaskRead,
    RuntimeTelemetryRead,
)
from backend.services.knowledge_service import KnowledgeService
from orchestration.knowledge_manager.knowledge_manager import RuntimeKnowledgeManager
from orchestration.runtime.runtime import RuntimeOrchestrator


class RuntimeService:
    def __init__(self, *, session, settings: Settings, redis_client=None, knowledge_service: KnowledgeService | None = None) -> None:
        self.orchestrator = RuntimeOrchestrator(
            settings=settings,
            agent_repository=RuntimeAgentRepository(session),
            conversation_repository=RuntimeConversationRepository(session),
            message_repository=RuntimeConversationMessageRepository(session),
            task_repository=RuntimeTaskRepository(session),
            task_step_repository=RuntimeTaskStepRepository(session),
            approval_repository=RuntimeApprovalRepository(session),
            event_repository=RuntimeEventRepository(session),
            telemetry_repository=RuntimeTelemetryRepository(session),
            knowledge_manager=RuntimeKnowledgeManager(knowledge_service) if knowledge_service is not None else None,
            redis_client=redis_client,
        )

    def register_agent(self, organization_id: UUID, payload: RuntimeAgentCreate) -> RuntimeAgentRead:
        return self.orchestrator.register_agent(organization_id, payload)

    def list_agents(self, organization_id: UUID) -> list[RuntimeAgentRead]:
        return self.orchestrator.list_agents(organization_id)

    def get_agent(self, organization_id: UUID, agent_id: UUID) -> RuntimeAgentRead:
        return self.orchestrator.get_agent(organization_id, agent_id)

    def plan_task(self, *, organization_id: UUID, request: RuntimeTaskCreate, current_user) -> tuple[RuntimeTaskRead, RuntimePlanRead]:
        task, plan = self.orchestrator.plan_task(organization_id=organization_id, request=request, current_user=current_user)
        return self.orchestrator._serialize_task(task), self.orchestrator._serialize_plan(plan)

    async def execute_task(self, *, organization_id: UUID, request: RuntimeTaskExecutionRequest, current_user) -> RuntimeTaskExecutionResponse:
        return await self.orchestrator.execute_task(organization_id=organization_id, request=request, current_user=current_user)

    def list_tasks(self, organization_id: UUID) -> list[RuntimeTaskRead]:
        return self.orchestrator.list_tasks(organization_id)

    def get_task(self, organization_id: UUID, task_id: UUID) -> RuntimeTaskRead:
        return self.orchestrator.get_task(organization_id, task_id)

    def list_conversations(self, organization_id: UUID) -> list[RuntimeConversationRead]:
        return self.orchestrator.list_conversations(organization_id)

    def get_conversation(self, organization_id: UUID, conversation_id: UUID) -> RuntimeConversationRead:
        return self.orchestrator.get_conversation(organization_id, conversation_id)

    def list_events(self, organization_id: UUID, limit: int = 100) -> list[RuntimeEventRead]:
        return self.orchestrator.list_events(organization_id, limit=limit)

    def list_telemetry(self, organization_id: UUID, task_id: UUID) -> list[RuntimeTelemetryRead]:
        return self.orchestrator.list_telemetry(organization_id, task_id)

    def get_status(self, organization_id: UUID) -> RuntimeStatusResponse:
        return self.orchestrator.get_status(organization_id)

    def approve(self, organization_id: UUID, payload: RuntimeApprovalCreate, *, decided_by: UUID | None = None) -> RuntimeApprovalRead:
        return self.orchestrator.approve(organization_id, payload, decided_by=decided_by)

    def reject(self, organization_id: UUID, payload: RuntimeApprovalCreate, *, decided_by: UUID | None = None) -> RuntimeApprovalRead:
        return self.orchestrator.reject(organization_id, payload, decided_by=decided_by)
