from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.database.models.runtime import RuntimeStepType
from orchestration.approval_engine.approval_engine import ApprovalDecision, ApprovalEngine, ApprovalMode, ApprovalPolicy, DefaultApprovalEngine
from orchestration.conversation_manager.conversation_manager import ConversationAction, ConversationManager
from orchestration.event_bus.event_bus import EventBus, RuntimeEventMessage, RuntimeEventName, InMemoryEventBus
from orchestration.knowledge_manager.knowledge_manager import KnowledgeContext, RuntimeKnowledgeManager
from orchestration.memory_manager.memory_manager import MemoryManager, MemoryRecord, MemoryScope
from orchestration.planner.planner import ExecutionPlan, PlanStep
from orchestration.telemetry.telemetry import TelemetryCollector
from orchestration.tool_manager.tool_manager import ToolManager, ToolResult
from orchestration.workflow_engine.workflow_engine import WorkflowEngine, WorkflowRunResult, WorkflowStepResult


@dataclass(slots=True)
class ExecutionContext:
    organization_id: UUID
    task_id: UUID | None = None
    conversation_id: UUID | None = None
    agent_id: UUID | None = None
    user_id: UUID | None = None
    knowledge_base_id: UUID | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionOutcome:
    plan: ExecutionPlan
    workflow: WorkflowRunResult
    result_json: dict[str, Any] = field(default_factory=dict)
    approval: ApprovalDecision | None = None
    knowledge: KnowledgeContext | None = None


class RuntimeExecutor:
    def __init__(
        self,
        *,
        tool_manager: ToolManager | None = None,
        memory_manager: MemoryManager | None = None,
        knowledge_manager: RuntimeKnowledgeManager | None = None,
        approval_engine: ApprovalEngine | None = None,
        conversation_manager: ConversationManager | None = None,
        telemetry: TelemetryCollector | None = None,
        event_bus: EventBus | None = None,
        workflow_engine: WorkflowEngine | None = None,
    ) -> None:
        self.tool_manager = tool_manager or ToolManager()
        self.memory_manager = memory_manager or MemoryManager()
        self.knowledge_manager = knowledge_manager
        self.approval_engine = approval_engine or DefaultApprovalEngine()
        self.conversation_manager = conversation_manager
        self.telemetry = telemetry or TelemetryCollector()
        self.event_bus = event_bus or InMemoryEventBus()
        self.workflow_engine = workflow_engine or WorkflowEngine()

    async def execute(
        self,
        *,
        plan: ExecutionPlan,
        context: ExecutionContext,
        current_user=None,
        knowledge_request=None,
        approval_policy: ApprovalPolicy | None = None,
    ) -> ExecutionOutcome:
        knowledge_context = None
        if self.knowledge_manager is not None and knowledge_request is not None and current_user is not None:
            knowledge_context = self.knowledge_manager.retrieve(current_user=current_user, request=knowledge_request, actor_user_id=context.user_id)
            await self.event_bus.publish(
                RuntimeEventMessage(
                    name=RuntimeEventName.KNOWLEDGE_RETRIEVED,
                    organization_id=context.organization_id,
                    task_id=context.task_id,
                    conversation_id=context.conversation_id,
                    agent_id=context.agent_id,
                    payload_json={"result_count": len(knowledge_context.results)},
                )
            )

        memory_records = self.memory_manager.retrieve(
            organization_id=context.organization_id,
            conversation_id=context.conversation_id,
            agent_id=context.agent_id,
            query=plan.task,
        )
        if memory_records.records:
            await self.event_bus.publish(
                RuntimeEventMessage(
                    name=RuntimeEventName.MEMORY_RETRIEVED,
                    organization_id=context.organization_id,
                    task_id=context.task_id,
                    conversation_id=context.conversation_id,
                    agent_id=context.agent_id,
                    payload_json={"retrieved_count": len(memory_records.records)},
                )
            )

        if self.conversation_manager is not None and context.conversation_id is not None:
            self.conversation_manager.record_message(
                conversation_id=context.conversation_id,
                organization_id=context.organization_id,
                role="system",
                content=plan.task,
                action_name="task_received",
            )

        async def run_step(step: PlanStep, state: dict[str, Any]) -> WorkflowStepResult:
            step_started = asyncio.get_event_loop().time()
            approval = self.approval_engine.decide(
                action_name=step.tool_name or step.name,
                confidence=float(state.get("confidence", 1.0)),
                policy=approval_policy,
                metadata_json={"step": step.name},
            )
            if step.requires_approval and not approval.approved:
                await self.event_bus.publish(
                    RuntimeEventMessage(
                        name=RuntimeEventName.AGENT_ESCALATED,
                        organization_id=context.organization_id,
                        task_id=context.task_id,
                        conversation_id=context.conversation_id,
                        agent_id=context.agent_id,
                        payload_json={"step": step.name, "reason": approval.reason},
                    )
                )
                return WorkflowStepResult(name=step.name, step_type=step.step_type, success=False, error=approval.reason, output_json={"approval": approval.status.value})

            if step.step_type == RuntimeStepType.KNOWLEDGE and knowledge_context is not None:
                output = {"citations": [citation.metadata_json for citation in knowledge_context.citations]}
                await self.event_bus.publish(RuntimeEventMessage(name=RuntimeEventName.KNOWLEDGE_RETRIEVED, organization_id=context.organization_id, task_id=context.task_id, conversation_id=context.conversation_id, agent_id=context.agent_id, payload_json=output))
                return WorkflowStepResult(name=step.name, step_type=step.step_type, success=True, output_json=output)

            if step.step_type == RuntimeStepType.MEMORY:
                output = {"memory_count": len(memory_records.records), "compressed_context": memory_records.compressed_context}
                return WorkflowStepResult(name=step.name, step_type=step.step_type, success=True, output_json=output)

            if step.step_type == RuntimeStepType.TOOL and step.tool_name:
                await self.event_bus.publish(
                    RuntimeEventMessage(
                        name=RuntimeEventName.TOOL_CALLED,
                        organization_id=context.organization_id,
                        task_id=context.task_id,
                        conversation_id=context.conversation_id,
                        agent_id=context.agent_id,
                        payload_json={"tool_name": step.tool_name, "arguments": step.arguments},
                    )
                )
                tool_result = await self.tool_manager.execute(step.tool_name, step.arguments)
                if not tool_result.success and step.retry_limit > 0:
                    tool_result = await self.tool_manager.retry(step.tool_name, step.arguments, attempts=step.retry_limit + 1)
                if not tool_result.success:
                    await self.event_bus.publish(
                        RuntimeEventMessage(
                            name=RuntimeEventName.TOOL_FAILED,
                            organization_id=context.organization_id,
                            task_id=context.task_id,
                            conversation_id=context.conversation_id,
                            agent_id=context.agent_id,
                            payload_json={"tool_name": step.tool_name, "error": tool_result.error},
                        )
                    )
                self.telemetry.record_latency(
                    organization_id=context.organization_id,
                    task_id=context.task_id,
                    metric_name=f"tool:{step.tool_name}",
                    latency_ms=tool_result.latency_ms,
                    metadata_json={"success": tool_result.success},
                )
                if self.conversation_manager is not None and context.conversation_id is not None:
                    self.conversation_manager.record_action(
                        conversation_id=context.conversation_id,
                        organization_id=context.organization_id,
                        action=ConversationAction(
                            name=step.tool_name,
                            payload_json=tool_result.output,
                            latency_ms=tool_result.latency_ms,
                            confidence=1.0 if tool_result.success else 0.0,
                        ),
                    )
                return WorkflowStepResult(
                    name=step.name,
                    step_type=step.step_type,
                    success=tool_result.success,
                    output_json=tool_result.output,
                    error=tool_result.error,
                    retries=tool_result.retries,
                )

            if step.step_type == RuntimeStepType.HUMAN_APPROVAL:
                return WorkflowStepResult(name=step.name, step_type=step.step_type, success=True, output_json={"status": "awaited"})

            if step.step_type == RuntimeStepType.LOG:
                return WorkflowStepResult(name=step.name, step_type=step.step_type, success=True, output_json={"logged": True})

            await asyncio.sleep(0)
            latency_ms = int((asyncio.get_event_loop().time() - step_started) * 1000)
            return WorkflowStepResult(name=step.name, step_type=step.step_type, success=True, output_json={"latency_ms": latency_ms})

        workflow = await self.workflow_engine.execute(plan, run_step)
        if workflow.success:
            await self.event_bus.publish(
                RuntimeEventMessage(
                    name=RuntimeEventName.TASK_COMPLETED,
                    organization_id=context.organization_id,
                    task_id=context.task_id,
                    conversation_id=context.conversation_id,
                    agent_id=context.agent_id,
                    payload_json={"step_count": len(workflow.step_results)},
                )
            )
        return ExecutionOutcome(
            plan=plan,
            workflow=workflow,
            result_json={"step_count": len(workflow.step_results), "success": workflow.success},
            approval=None,
            knowledge=knowledge_context,
        )
