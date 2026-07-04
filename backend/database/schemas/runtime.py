from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from backend.database.models.runtime import (
    RuntimeApprovalStatus,
    RuntimeConversationStatus,
    RuntimeEventType,
    RuntimeStepType,
    RuntimeTaskStatus,
)
from backend.database.schemas.common import TimestampedSchema


class RuntimeAgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    role: str = Field(min_length=2, max_length=128)
    description: str | None = Field(default=None, max_length=5000)
    allowed_tools: list[str] = Field(default_factory=list)
    required_integrations: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    max_context: int = Field(default=8192, ge=1)
    temperature: float = Field(default=0.2, ge=0, le=2)
    enabled: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeAgentRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    name: str
    role: str
    description: str | None = None
    allowed_tools: list[str]
    required_integrations: list[str]
    system_prompt: str | None = None
    capabilities: list[str]
    max_context: int
    temperature: float
    enabled: bool
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimePlanStepRead(BaseModel):
    name: str
    description: str | None = None
    step_type: RuntimeStepType
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    retry_limit: int = 0
    timeout_seconds: int | None = None


class RuntimePlanRead(BaseModel):
    task: str
    agent_id: UUID | None = None
    steps: list[RuntimePlanStepRead] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeTaskCreate(BaseModel):
    agent_id: UUID | None = None
    conversation_id: UUID | None = None
    task: str = Field(min_length=1, max_length=10000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeTaskStepRead(BaseModel):
    id: UUID
    task_id: UUID
    organization_id: UUID
    step_index: int
    step_type: RuntimeStepType
    name: str
    description: str | None = None
    status: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    retry_count: int
    timeout_seconds: int | None = None


class RuntimeTaskRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    agent_id: UUID | None = None
    conversation_id: UUID | None = None
    status: RuntimeTaskStatus
    task_text: str
    plan_json: dict[str, Any]
    current_step_index: int
    error_message: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    steps: list[RuntimeTaskStepRead] = Field(default_factory=list)


class RuntimeTaskExecutionRequest(BaseModel):
    task: str = Field(min_length=1, max_length=10000)
    agent_id: UUID | None = None
    conversation_id: UUID | None = None
    knowledge_base_id: UUID | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeTaskExecutionResponse(BaseModel):
    task: RuntimeTaskRead
    plan: RuntimePlanRead
    result: dict[str, Any]


class RuntimeConversationMessageRead(TimestampedSchema):
    id: UUID
    conversation_id: UUID
    organization_id: UUID
    role: str
    content: str
    tool_name: str | None = None
    tool_payload: dict[str, Any]
    action_name: str | None = None
    cost: float
    latency_ms: int
    confidence: float


class RuntimeConversationRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    agent_id: UUID | None = None
    external_conversation_id: str | None = None
    title: str | None = None
    status: RuntimeConversationStatus
    context_summary: str | None = None
    total_cost: float
    total_latency_ms: int
    confidence: float
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    messages: list[RuntimeConversationMessageRead] = Field(default_factory=list)


class RuntimeEventRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    task_id: UUID | None = None
    conversation_id: UUID | None = None
    agent_id: UUID | None = None
    event_type: RuntimeEventType
    payload_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeApprovalCreate(BaseModel):
    task_id: UUID | None = None
    step_id: UUID | None = None
    requested_action: str
    reason: str | None = None
    policy_name: str = "default"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeApprovalRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    task_id: UUID | None = None
    step_id: UUID | None = None
    requested_action: str
    reason: str | None = None
    policy_name: str
    status: RuntimeApprovalStatus
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeApprovalDecision(BaseModel):
    status: RuntimeApprovalStatus
    decided_by: UUID | None = None
    reason: str | None = None


class RuntimeTelemetryRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    task_id: UUID | None = None
    conversation_id: UUID | None = None
    agent_id: UUID | None = None
    metric_name: str
    metric_value: float
    unit: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuntimeStatusResponse(BaseModel):
    agents: int
    tasks: int
    conversations: int
    events: int
    approvals: int
    telemetry: int
