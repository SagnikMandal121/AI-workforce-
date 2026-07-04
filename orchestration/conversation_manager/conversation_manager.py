from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.database.models.runtime import RuntimeConversation, RuntimeConversationMessage
from backend.database.repositories.runtime import RuntimeConversationMessageRepository, RuntimeConversationRepository


@dataclass(slots=True)
class ConversationAction:
    name: str
    payload_json: dict[str, Any] = field(default_factory=dict)
    cost: float = 0.0
    latency_ms: int = 0
    confidence: float = 0.0


class ConversationManager:
    def __init__(self, conversation_repository: RuntimeConversationRepository, message_repository: RuntimeConversationMessageRepository) -> None:
        self.conversations = conversation_repository
        self.messages = message_repository

    def create_conversation(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID | None = None,
        title: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> RuntimeConversation:
        conversation = RuntimeConversation(
            organization_id=organization_id,
            agent_id=agent_id,
            title=title,
            metadata_json=metadata_json or {},
        )
        return self.conversations.create(conversation)

    def record_message(
        self,
        *,
        conversation_id: UUID,
        organization_id: UUID,
        role: str,
        content: str,
        tool_name: str | None = None,
        tool_payload: dict[str, Any] | None = None,
        action_name: str | None = None,
        cost: float = 0.0,
        latency_ms: int = 0,
        confidence: float = 0.0,
    ) -> RuntimeConversationMessage:
        message = RuntimeConversationMessage(
            conversation_id=conversation_id,
            organization_id=organization_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_payload=tool_payload or {},
            action_name=action_name,
            cost=cost,
            latency_ms=latency_ms,
            confidence=confidence,
        )
        stored = self.messages.create(message)
        self._update_conversation_metrics(conversation_id, cost=cost, latency_ms=latency_ms, confidence=confidence)
        return stored

    def record_action(self, *, conversation_id: UUID, organization_id: UUID, action: ConversationAction) -> RuntimeConversationMessage:
        return self.record_message(
            conversation_id=conversation_id,
            organization_id=organization_id,
            role="action",
            content=action.name,
            action_name=action.name,
            tool_payload=action.payload_json,
            cost=action.cost,
            latency_ms=action.latency_ms,
            confidence=action.confidence,
        )

    def summarize(self, conversation_id: UUID) -> str:
        messages = self.messages.list_by_conversation(conversation_id)
        summary_lines = [message.content for message in messages[-10:]]
        return "\n".join(summary_lines)

    def update_summary(self, conversation: RuntimeConversation) -> RuntimeConversation:
        conversation.context_summary = self.summarize(conversation.id)
        conversation.updated_at = datetime.now(UTC)
        return conversation

    def _update_conversation_metrics(self, conversation_id: UUID, *, cost: float, latency_ms: int, confidence: float) -> None:
        conversation = self.conversations.get_by_id(conversation_id)
        if conversation is None:
            return
        conversation.total_cost = float(conversation.total_cost or 0) + float(cost)
        conversation.total_latency_ms = int(conversation.total_latency_ms or 0) + int(latency_ms)
        conversation.confidence = max(float(conversation.confidence or 0), float(confidence))
        conversation.updated_at = datetime.now(UTC)
