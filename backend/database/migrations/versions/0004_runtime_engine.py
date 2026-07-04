"""Runtime orchestration schema.

Revision ID: 0004_runtime_engine
Revises: 0003_knowledge_engine
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_runtime_engine"
down_revision = "0003_knowledge_engine"
branch_labels = None
depends_on = None


runtime_task_status = sa.Enum(
    "pending",
    "planned",
    "running",
    "waiting_approval",
    "completed",
    "failed",
    "cancelled",
    name="runtime_task_status",
)
runtime_step_type = sa.Enum(
    "sequential",
    "parallel",
    "conditional",
    "retry",
    "loop",
    "human_approval",
    "timeout",
    "tool",
    "memory",
    "knowledge",
    "llm",
    "log",
    name="runtime_step_type",
)
runtime_approval_status = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "escalated",
    name="runtime_approval_status",
)
runtime_event_type = sa.Enum(
    "task_started",
    "tool_called",
    "tool_failed",
    "task_completed",
    "agent_escalated",
    "knowledge_retrieved",
    "approval_requested",
    "approval_decided",
    "memory_retrieved",
    "metric_recorded",
    name="runtime_event_type",
)
runtime_conversation_status = sa.Enum(
    "open",
    "archived",
    "closed",
    name="runtime_conversation_status",
)


def upgrade() -> None:
    op.create_table(
        "runtime_agents",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("allowed_tools", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("required_integrations", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("max_context", sa.Integer(), nullable=False, server_default=sa.text("'8192'")),
        sa.Column("temperature", sa.Float(), nullable=False, server_default=sa.text("'0.2'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name", name="uq_runtime_agents_org_name"),
    )
    op.create_index("ix_runtime_agents_org_enabled", "runtime_agents", ["organization_id", "enabled"])

    op.create_table(
        "runtime_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_conversation_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", runtime_conversation_status, nullable=False, server_default=sa.text("'open'")),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_runtime_conversations_org_status", "runtime_conversations", ["organization_id", "status"])

    op.create_table(
        "runtime_conversation_messages",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("runtime_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=True),
        sa.Column("tool_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("action_name", sa.String(length=255), nullable=True),
        sa.Column("cost", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_runtime_conversation_messages_conversation",
        "runtime_conversation_messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "runtime_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("runtime_conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", runtime_task_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("task_text", sa.Text(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_runtime_tasks_org_status", "runtime_tasks", ["organization_id", "status"])

    op.create_table(
        "runtime_task_steps",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_type", runtime_step_type, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("input_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("task_id", "step_index", name="uq_runtime_task_steps_task_index"),
    )
    op.create_index("ix_runtime_task_steps_task_status", "runtime_task_steps", ["task_id", "status"])

    op.create_table(
        "runtime_events",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("runtime_conversations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", runtime_event_type, nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_runtime_events_org_created_at", "runtime_events", ["organization_id", "created_at"])

    op.create_table(
        "runtime_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("step_id", sa.Uuid(), sa.ForeignKey("runtime_task_steps.id", ondelete="CASCADE"), nullable=True),
        sa.Column("requested_action", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("policy_name", sa.String(length=128), nullable=False),
        sa.Column("status", runtime_approval_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("decided_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_runtime_approvals_org_status", "runtime_approvals", ["organization_id", "status"])

    op.create_table(
        "runtime_telemetry",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("runtime_tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("runtime_conversations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("runtime_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_runtime_telemetry_org_created_at", "runtime_telemetry", ["organization_id", "created_at"])
    op.create_index("ix_runtime_telemetry_task_created_at", "runtime_telemetry", ["task_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_runtime_telemetry_task_created_at", table_name="runtime_telemetry")
    op.drop_index("ix_runtime_telemetry_org_created_at", table_name="runtime_telemetry")
    op.drop_table("runtime_telemetry")

    op.drop_index("ix_runtime_approvals_org_status", table_name="runtime_approvals")
    op.drop_table("runtime_approvals")

    op.drop_index("ix_runtime_events_org_created_at", table_name="runtime_events")
    op.drop_table("runtime_events")

    op.drop_index("ix_runtime_task_steps_task_status", table_name="runtime_task_steps")
    op.drop_table("runtime_task_steps")

    op.drop_index("ix_runtime_tasks_org_status", table_name="runtime_tasks")
    op.drop_table("runtime_tasks")

    op.drop_index("ix_runtime_conversation_messages_conversation", table_name="runtime_conversation_messages")
    op.drop_table("runtime_conversation_messages")

    op.drop_index("ix_runtime_conversations_org_status", table_name="runtime_conversations")
    op.drop_table("runtime_conversations")

    op.drop_index("ix_runtime_agents_org_enabled", table_name="runtime_agents")
    op.drop_table("runtime_agents")

    runtime_event_type.drop(op.get_bind(), checkfirst=False)
    runtime_approval_status.drop(op.get_bind(), checkfirst=False)
    runtime_step_type.drop(op.get_bind(), checkfirst=False)
    runtime_task_status.drop(op.get_bind(), checkfirst=False)
    runtime_conversation_status.drop(op.get_bind(), checkfirst=False)
