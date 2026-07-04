from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from backend.database.models.runtime import RuntimeStepType


@dataclass(slots=True)
class PlanStep:
    name: str
    description: str | None = None
    step_type: RuntimeStepType = RuntimeStepType.SEQUENTIAL
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    retry_limit: int = 0
    timeout_seconds: int | None = None


@dataclass(slots=True)
class ExecutionPlan:
    task: str
    agent_id: UUID | None = None
    steps: list[PlanStep] = field(default_factory=list)
    metadata_json: dict[str, Any] = field(default_factory=dict)


class Planner(Protocol):
    def plan(self, *, task: str, agent: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> ExecutionPlan: ...


class RuleBasedPlanner:
    def plan(self, *, task: str, agent: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> ExecutionPlan:
        task_text = task.strip()
        lower_task = task_text.lower()
        steps: list[PlanStep]
        if any(keyword in lower_task for keyword in ("reply email", "respond to email", "email reply", "draft email")):
            steps = [
                PlanStep(name="Read email", description="Inspect the source message", step_type=RuntimeStepType.SEQUENTIAL),
                PlanStep(name="Retrieve context", description="Pull knowledge and memory context", step_type=RuntimeStepType.KNOWLEDGE),
                PlanStep(name="Draft response", description="Compose a response draft", step_type=RuntimeStepType.LLM, requires_approval=True),
                PlanStep(name="Approval", description="Request human approval", step_type=RuntimeStepType.HUMAN_APPROVAL, requires_approval=True),
                PlanStep(name="Send", description="Send the approved response", step_type=RuntimeStepType.TOOL, tool_name="email.send"),
            ]
        elif any(keyword in lower_task for keyword in ("schedule", "calendar", "meeting")):
            steps = [
                PlanStep(name="Check availability", step_type=RuntimeStepType.TOOL, tool_name="calendar.availability"),
                PlanStep(name="Propose times", step_type=RuntimeStepType.LLM, requires_approval=True),
                PlanStep(name="Approval", step_type=RuntimeStepType.HUMAN_APPROVAL, requires_approval=True),
                PlanStep(name="Update calendar", step_type=RuntimeStepType.TOOL, tool_name="calendar.create"),
            ]
        else:
            steps = [
                PlanStep(name="Interpret task", description="Clarify the objective", step_type=RuntimeStepType.SEQUENTIAL),
                PlanStep(name="Retrieve context", description="Load memory and knowledge", step_type=RuntimeStepType.KNOWLEDGE),
                PlanStep(name="Draft action", description="Prepare a draft result", step_type=RuntimeStepType.LLM, requires_approval=True),
                PlanStep(name="Approval", description="Request approval if required", step_type=RuntimeStepType.HUMAN_APPROVAL, requires_approval=True),
                PlanStep(name="Execute", description="Run the selected tool or action", step_type=RuntimeStepType.TOOL),
                PlanStep(name="Log", description="Persist the outcome", step_type=RuntimeStepType.LOG),
            ]
        return ExecutionPlan(
            task=task_text,
            agent_id=agent.get("id") if agent else None,
            steps=steps,
            metadata_json={
                "agent_role": agent.get("role") if agent else None,
                "allowed_tools": agent.get("allowed_tools") if agent else [],
                "capabilities": agent.get("capabilities") if agent else [],
                "context_size": len(context or {}),
            },
        )
