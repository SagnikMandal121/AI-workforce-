from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from database.models.common import TimeStampedMixin, UUIDMixin


class RuntimeTaskStatus(str, Enum):
    PENDING = "pending"
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeStepType(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    RETRY = "retry"
    LOOP = "loop"
    HUMAN_APPROVAL = "human_approval"
    TIMEOUT = "timeout"
    TOOL = "tool"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    LLM = "llm"
    LOG = "log"


class RuntimeApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class RuntimeEventType(str, Enum):
    TASK_STARTED = "task_started"
    TOOL_CALLED = "tool_called"
    TOOL_FAILED = "tool_failed"
    TASK_COMPLETED = "task_completed"
    AGENT_ESCALATED = "agent_escalated"
    KNOWLEDGE_RETRIEVED = "knowledge_retrieved"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"
    MEMORY_RETRIEVED = "memory_retrieved"
    METRIC_RECORDED = "metric_recorded"


class RuntimeConversationStatus(str, Enum):
    OPEN = "open"
    ARCHIVED = "archived"
    CLOSED = "closed"


class RuntimeAgent(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_agents"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_runtime_agents_org_name"),
        Index("ix_runtime_agents_org_enabled", "organization_id", "enabled"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_integrations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_context: Mapped[int] = mapped_column(Integer, default=8192, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    conversations = relationship("RuntimeConversation", back_populates="agent")
    tasks = relationship("RuntimeTask", back_populates="agent")


class RuntimeConversation(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_conversations"
    __table_args__ = (Index("ix_runtime_conversations_org_status", "organization_id", "status"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True)
    external_conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[RuntimeConversationStatus] = mapped_column(
        SAEnum(
            RuntimeConversationStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=RuntimeConversationStatus.OPEN,
        nullable=False,
    )
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    agent = relationship("RuntimeAgent", back_populates="conversations")
    messages = relationship("RuntimeConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    tasks = relationship("RuntimeTask", back_populates="conversation")


class RuntimeConversationMessage(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_conversation_messages"
    __table_args__ = (Index("ix_runtime_conversation_messages_conversation", "conversation_id", "created_at"),)

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("runtime_conversations.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    action_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    conversation = relationship("RuntimeConversation", back_populates="messages")


class RuntimeTask(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_tasks"
    __table_args__ = (Index("ix_runtime_tasks_org_status", "organization_id", "status"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runtime_conversations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[RuntimeTaskStatus] = mapped_column(
        SAEnum(
            RuntimeTaskStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=RuntimeTaskStatus.PENDING,
        nullable=False,
    )
    task_text: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    agent = relationship("RuntimeAgent", back_populates="tasks")
    conversation = relationship("RuntimeConversation", back_populates="tasks")
    steps = relationship("RuntimeTaskStep", back_populates="task", cascade="all, delete-orphan")
    events = relationship("RuntimeEvent", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("RuntimeApproval", back_populates="task", cascade="all, delete-orphan")
    telemetry = relationship("RuntimeTelemetry", back_populates="task", cascade="all, delete-orphan")


class RuntimeTaskStep(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_task_steps"
    __table_args__ = (
        UniqueConstraint("task_id", "step_index", name="uq_runtime_task_steps_task_index"),
        Index("ix_runtime_task_steps_task_status", "task_id", "status"),
    )

    task_id: Mapped[UUID] = mapped_column(ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[RuntimeStepType] = mapped_column(
        SAEnum(
            RuntimeStepType,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task = relationship("RuntimeTask", back_populates="steps")


class RuntimeEvent(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_events"
    __table_args__ = (Index("ix_runtime_events_org_created_at", "organization_id", "created_at"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runtime_conversations.id", ondelete="CASCADE"), nullable=True
    )
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[RuntimeEventType] = mapped_column(
        SAEnum(
            RuntimeEventType,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    task = relationship("RuntimeTask", back_populates="events")


class RuntimeApproval(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_approvals"
    __table_args__ = (Index("ix_runtime_approvals_org_status", "organization_id", "status"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=True)
    step_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runtime_task_steps.id", ondelete="CASCADE"), nullable=True
    )
    requested_action: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[RuntimeApprovalStatus] = mapped_column(
        SAEnum(
            RuntimeApprovalStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=RuntimeApprovalStatus.PENDING,
        nullable=False,
    )
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    task = relationship("RuntimeTask", back_populates="approvals")


class RuntimeTelemetry(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "runtime_telemetry"
    __table_args__ = (
        Index("ix_runtime_telemetry_org_created_at", "organization_id", "created_at"),
        Index("ix_runtime_telemetry_task_created_at", "task_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runtime_conversations.id", ondelete="CASCADE"), nullable=True
    )
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    task = relationship("RuntimeTask", back_populates="telemetry")
