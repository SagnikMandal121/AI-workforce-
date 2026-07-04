from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from backend.core.config import Settings
from backend.core.exceptions import NotFoundError
from backend.database.models.runtime import (
    RuntimeApproval,
    RuntimeApprovalStatus,
    RuntimeAgent,
    RuntimeConversation,
    RuntimeConversationStatus,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTask,
    RuntimeTaskStatus,
    RuntimeTaskStep,
    RuntimeTelemetry,
)
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
    RuntimeApprovalDecision,
    RuntimeApprovalRead,
    RuntimeConversationRead,
    RuntimeEventRead,
    RuntimePlanRead,
    RuntimePlanStepRead,
    RuntimeStatusResponse,
    RuntimeTaskCreate,
    RuntimeTaskExecutionRequest,
    RuntimeTaskExecutionResponse,
    RuntimeTaskRead,
    RuntimeTaskStepRead,
    RuntimeTelemetryRead,
)
from orchestration.agent_registry.agent_registry import SQLAlchemyAgentRegistry
from orchestration.approval_engine.approval_engine import ApprovalMode, ApprovalPolicy, DefaultApprovalEngine
from orchestration.conversation_manager.conversation_manager import ConversationManager
from orchestration.event_bus.event_bus import EventBus, InMemoryEventBus, RuntimeEventMessage, RuntimeEventName
from orchestration.executor.executor import ExecutionContext, RuntimeExecutor
from orchestration.knowledge_manager.knowledge_manager import RuntimeKnowledgeManager
from orchestration.memory_manager.memory_manager import MemoryManager
from orchestration.planner.planner import ExecutionPlan, PlanStep, RuleBasedPlanner
from orchestration.telemetry.telemetry import TelemetryCollector
from orchestration.tool_manager.tool_manager import ToolManager
from orchestration.workflow_engine.workflow_engine import WorkflowEngine


class RuntimeOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        agent_repository: RuntimeAgentRepository,
        conversation_repository: RuntimeConversationRepository,
        message_repository: RuntimeConversationMessageRepository,
        task_repository: RuntimeTaskRepository,
        task_step_repository: RuntimeTaskStepRepository,
        approval_repository: RuntimeApprovalRepository,
        event_repository: RuntimeEventRepository,
        telemetry_repository: RuntimeTelemetryRepository,
        knowledge_manager: RuntimeKnowledgeManager | None = None,
        redis_client=None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.settings = settings
        self.agent_registry = SQLAlchemyAgentRegistry(agent_repository)
        self.conversations = ConversationManager(conversation_repository, message_repository)
        self.tasks = task_repository
        self.task_steps = task_step_repository
        self.approvals = approval_repository
        self.events = event_repository
        self.telemetry = telemetry_repository
        self.memory = MemoryManager(redis_client)
        self.knowledge = knowledge_manager
        self.planner = RuleBasedPlanner()
        self.tools = ToolManager()
        self.approval_engine = DefaultApprovalEngine()
        self.workflow = WorkflowEngine()
        self.event_bus = event_bus or InMemoryEventBus()
        self.executor = RuntimeExecutor(
            tool_manager=self.tools,
            memory_manager=self.memory,
            knowledge_manager=self.knowledge,
            approval_engine=self.approval_engine,
            conversation_manager=self.conversations,
            telemetry=TelemetryCollector(),
            event_bus=self.event_bus,
            workflow_engine=self.workflow,
        )

    def register_agent(self, organization_id: UUID, payload: RuntimeAgentCreate) -> RuntimeAgentRead:
        profile = self.agent_registry.register(organization_id=organization_id, payload=payload)
        return self._serialize_agent(profile)

    def list_agents(self, organization_id: UUID) -> list[RuntimeAgentRead]:
        return [self._serialize_agent(agent) for agent in self.agent_registry.list_agents(organization_id=organization_id)]

    def get_agent(self, organization_id: UUID, agent_id: UUID) -> RuntimeAgentRead:
        agent = self.agent_registry.load(organization_id=organization_id, agent_id=agent_id)
        if agent is None:
            raise NotFoundError("Agent not found")
        return self._serialize_agent(agent)

    def plan_task(self, *, organization_id: UUID, request: RuntimeTaskCreate, current_user, metadata_json: dict[str, Any] | None = None) -> tuple[RuntimeTask, ExecutionPlan]:
        agent_profile = None
        if request.agent_id is not None:
            agent_profile = self.agent_registry.load(organization_id=organization_id, agent_id=request.agent_id)
        plan = self.planner.plan(task=request.task, agent=asdict(agent_profile) if agent_profile else None, context=request.metadata_json)
        task = RuntimeTask(
            organization_id=organization_id,
            agent_id=request.agent_id,
            conversation_id=request.conversation_id,
            status=RuntimeTaskStatus.PLANNED,
            task_text=request.task,
            plan_json=self._serialize_plan(plan).model_dump(mode="json"),
            metadata_json=metadata_json or request.metadata_json,
        )
        self.tasks.create(task)
        self.task_steps.create_many(self._build_task_steps(task, plan))
        self.events.create(
            RuntimeEvent(
                organization_id=organization_id,
                task_id=task.id,
                conversation_id=request.conversation_id,
                agent_id=request.agent_id,
                event_type=RuntimeEventType.TASK_STARTED,
                payload_json={"task": request.task},
            )
        )
        return task, plan

    async def execute_task(self, *, organization_id: UUID, request: RuntimeTaskExecutionRequest, current_user, approval_policy: ApprovalPolicy | None = None) -> RuntimeTaskExecutionResponse:
        task, plan = self.plan_task(
            organization_id=organization_id,
            request=RuntimeTaskCreate(
                agent_id=request.agent_id,
                conversation_id=request.conversation_id,
                task=request.task,
                metadata_json=request.metadata_json,
            ),
            current_user=current_user,
        )
        task.status = RuntimeTaskStatus.RUNNING
        knowledge_request = None
        if request.knowledge_base_id is not None:
            knowledge_request = SearchRequest(
                query=request.task,
                top_k=5,
                knowledge_base_id=request.knowledge_base_id,
            )
        event_count_before = len(self.event_bus.list_events()) if hasattr(self.event_bus, "list_events") else 0
        telemetry_count_before = len(self.executor.telemetry.list_records())
        outcome = await self.executor.execute(
            plan=plan,
            context=ExecutionContext(
                organization_id=organization_id,
                task_id=task.id,
                conversation_id=request.conversation_id,
                agent_id=request.agent_id,
                user_id=current_user.id,
                knowledge_base_id=request.knowledge_base_id,
                metadata_json=request.metadata_json,
            ),
            current_user=current_user,
            knowledge_request=knowledge_request,
            approval_policy=approval_policy,
        )
        task.status = RuntimeTaskStatus.COMPLETED if outcome.workflow.success else RuntimeTaskStatus.FAILED
        task.error_message = None if outcome.workflow.success else "Execution failed"
        self._apply_step_results(task, outcome.workflow.step_results)
        self._persist_events(organization_id, event_count_before)
        self._persist_telemetry(organization_id, telemetry_count_before, task.id, request.conversation_id, request.agent_id)
        self.tasks.session.commit()
        return RuntimeTaskExecutionResponse(
            task=self._serialize_task(task),
            plan=self._serialize_plan(plan),
            result=outcome.result_json,
        )

    def list_tasks(self, organization_id: UUID) -> list[RuntimeTaskRead]:
        return [self._serialize_task(task) for task in self.tasks.list_by_organization(organization_id)]

    def get_task(self, organization_id: UUID, task_id: UUID) -> RuntimeTaskRead:
        task = self.tasks.get_by_id(task_id)
        if task is None or task.organization_id != organization_id:
            raise NotFoundError("Task not found")
        return self._serialize_task(task)

    def list_conversations(self, organization_id: UUID) -> list[RuntimeConversationRead]:
        return [self._serialize_conversation(conversation) for conversation in self.conversations.conversations.list_by_organization(organization_id)]

    def get_conversation(self, organization_id: UUID, conversation_id: UUID) -> RuntimeConversationRead:
        conversation = self.conversations.conversations.get_by_id(conversation_id)
        if conversation is None or conversation.organization_id != organization_id:
            raise NotFoundError("Conversation not found")
        return self._serialize_conversation(conversation)

    def list_events(self, organization_id: UUID, limit: int = 100) -> list[RuntimeEventRead]:
        return [self._serialize_event(event) for event in self.events.list_by_organization(organization_id, limit=limit)]

    def list_telemetry(self, organization_id: UUID, task_id: UUID) -> list[RuntimeTelemetryRead]:
        task = self.tasks.get_by_id(task_id)
        if task is None or task.organization_id != organization_id:
            raise NotFoundError("Task not found")
        return [self._serialize_telemetry(entry) for entry in self.telemetry.list_by_task(task_id)]

    def get_status(self, organization_id: UUID) -> RuntimeStatusResponse:
        return RuntimeStatusResponse(
            agents=len(self.agent_registry.list_agents(organization_id=organization_id)),
            tasks=len(self.tasks.list_by_organization(organization_id)),
            conversations=len(self.conversations.conversations.list_by_organization(organization_id)),
            events=len(self.events.list_by_organization(organization_id)),
            approvals=len([approval for task in self.tasks.list_by_organization(organization_id) for approval in self.approvals.list_by_task(task.id)]),
            telemetry=len([entry for task in self.tasks.list_by_organization(organization_id) for entry in self.telemetry.list_by_task(task.id)]),
        )

    def approve(self, organization_id: UUID, payload: RuntimeApprovalCreate, *, decided_by: UUID | None = None) -> RuntimeApprovalRead:
        if payload.task_id is not None:
            task = self.tasks.get_by_id(payload.task_id)
            if task is None or task.organization_id != organization_id:
                raise NotFoundError("Task not found")
        approval = RuntimeApproval(
            organization_id=organization_id,
            task_id=payload.task_id,
            step_id=payload.step_id,
            requested_action=payload.requested_action,
            reason=payload.reason,
            policy_name=payload.policy_name,
            status=RuntimeApprovalStatus.APPROVED,
            decided_by=decided_by,
            decided_at=None,
            metadata_json=payload.metadata_json,
        )
        self.approvals.create(approval)
        self.approvals.session.commit()
        return self._serialize_approval(approval)

    def reject(self, organization_id: UUID, payload: RuntimeApprovalCreate, *, decided_by: UUID | None = None) -> RuntimeApprovalRead:
        if payload.task_id is not None:
            task = self.tasks.get_by_id(payload.task_id)
            if task is None or task.organization_id != organization_id:
                raise NotFoundError("Task not found")
        approval = RuntimeApproval(
            organization_id=organization_id,
            task_id=payload.task_id,
            step_id=payload.step_id,
            requested_action=payload.requested_action,
            reason=payload.reason,
            policy_name=payload.policy_name,
            status=RuntimeApprovalStatus.REJECTED,
            decided_by=decided_by,
            decided_at=None,
            metadata_json=payload.metadata_json,
        )
        self.approvals.create(approval)
        self.approvals.session.commit()
        return self._serialize_approval(approval)

    def _build_task_steps(self, task: RuntimeTask, plan: ExecutionPlan) -> list[RuntimeTaskStep]:
        steps: list[RuntimeTaskStep] = []
        for index, step in enumerate(plan.steps):
            steps.append(
                RuntimeTaskStep(
                    task_id=task.id,
                    organization_id=task.organization_id,
                    step_index=index,
                    step_type=step.step_type,
                    name=step.name,
                    description=step.description,
                    status="pending",
                    input_json=step.arguments,
                )
            )
        return steps

    def _apply_step_results(self, task: RuntimeTask, results: list[Any]) -> None:
        stored_steps = self.task_steps.list_by_task(task.id)
        for step_model, result in zip(stored_steps, results, strict=False):
            step_model.status = "completed" if result.success else "failed"
            step_model.output_json = result.output_json
            step_model.retry_count = result.retries
            if not result.success:
                task.status = RuntimeTaskStatus.FAILED
        task.current_step_index = max(len(results) - 1, 0)

    def _serialize_agent(self, agent) -> RuntimeAgentRead:
        return RuntimeAgentRead(
            id=agent.id,
            organization_id=agent.organization_id,
            name=agent.name,
            role=agent.role,
            description=agent.description,
            allowed_tools=list(agent.allowed_tools or []),
            required_integrations=list(agent.required_integrations or []),
            system_prompt=agent.system_prompt,
            capabilities=list(agent.capabilities or []),
            max_context=agent.max_context,
            temperature=float(agent.temperature),
            enabled=agent.enabled,
            metadata_json=dict(agent.metadata_json or {}),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    def _serialize_plan(self, plan: ExecutionPlan) -> RuntimePlanRead:
        return RuntimePlanRead(
            task=plan.task,
            agent_id=plan.agent_id,
            steps=[RuntimePlanStepRead(**asdict(step)) for step in plan.steps],
            metadata_json=plan.metadata_json,
        )

    def _serialize_task(self, task: RuntimeTask) -> RuntimeTaskRead:
        return RuntimeTaskRead(
            id=task.id,
            organization_id=task.organization_id,
            agent_id=task.agent_id,
            conversation_id=task.conversation_id,
            status=task.status,
            task_text=task.task_text,
            plan_json=task.plan_json,
            current_step_index=task.current_step_index,
            error_message=task.error_message,
            metadata_json=task.metadata_json,
            created_at=task.created_at,
            updated_at=task.updated_at,
            steps=[self._serialize_task_step(step) for step in self.task_steps.list_by_task(task.id)],
        )

    def _serialize_task_step(self, step: RuntimeTaskStep) -> RuntimeTaskStepRead:
        return RuntimeTaskStepRead(
            id=step.id,
            task_id=step.task_id,
            organization_id=step.organization_id,
            step_index=step.step_index,
            step_type=step.step_type,
            name=step.name,
            description=step.description,
            status=step.status,
            input_json=step.input_json,
            output_json=step.output_json,
            retry_count=step.retry_count,
            timeout_seconds=step.timeout_seconds,
        )

    def _serialize_conversation(self, conversation: RuntimeConversation) -> RuntimeConversationRead:
        return RuntimeConversationRead(
            id=conversation.id,
            organization_id=conversation.organization_id,
            agent_id=conversation.agent_id,
            external_conversation_id=conversation.external_conversation_id,
            title=conversation.title,
            status=conversation.status,
            context_summary=conversation.context_summary,
            total_cost=conversation.total_cost,
            total_latency_ms=conversation.total_latency_ms,
            confidence=conversation.confidence,
            metadata_json=conversation.metadata_json,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[
                RuntimeConversationMessageRead(
                    id=message.id,
                    conversation_id=message.conversation_id,
                    organization_id=message.organization_id,
                    role=message.role,
                    content=message.content,
                    tool_name=message.tool_name,
                    tool_payload=message.tool_payload,
                    action_name=message.action_name,
                    cost=message.cost,
                    latency_ms=message.latency_ms,
                    confidence=message.confidence,
                    created_at=message.created_at,
                    updated_at=message.updated_at,
                )
                for message in self.conversations.messages.list_by_conversation(conversation.id)
            ],
        )

    def _serialize_event(self, event: RuntimeEvent) -> RuntimeEventRead:
        return RuntimeEventRead.model_validate(event)

    def _serialize_approval(self, approval: RuntimeApproval) -> RuntimeApprovalRead:
        return RuntimeApprovalRead.model_validate(approval)

    def _serialize_telemetry(self, telemetry) -> RuntimeTelemetryRead:
        return RuntimeTelemetryRead.model_validate(telemetry)

    def _persist_events(self, organization_id: UUID, event_count_before: int) -> None:
        if not hasattr(self.event_bus, "list_events"):
            return
        events = self.event_bus.list_events()[event_count_before:]
        for event in events:
            self.events.create(
                RuntimeEvent(
                    organization_id=organization_id,
                    task_id=event.task_id,
                    conversation_id=event.conversation_id,
                    agent_id=event.agent_id,
                    event_type=RuntimeEventType(event.name.value.lower().replace(" ", "_")),
                    payload_json=event.payload_json,
                )
            )

    def _persist_telemetry(
        self,
        organization_id: UUID,
        telemetry_count_before: int,
        task_id: UUID,
        conversation_id: UUID | None,
        agent_id: UUID | None,
    ) -> None:
        records = self.executor.telemetry.list_records()[telemetry_count_before:]
        for record in records:
            self.telemetry.create(
                RuntimeTelemetry(
                    organization_id=organization_id,
                    task_id=task_id,
                    conversation_id=conversation_id,
                    agent_id=agent_id,
                    metric_name=record.metric_name,
                    metric_value=record.metric_value,
                    unit=record.unit,
                    metadata_json=record.metadata_json,
                )
            )
