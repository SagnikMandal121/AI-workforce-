from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4


class RuntimeEventName(str, Enum):
    TASK_STARTED = "Task Started"
    TOOL_CALLED = "Tool Called"
    TOOL_FAILED = "Tool Failed"
    TASK_COMPLETED = "Task Completed"
    AGENT_ESCALATED = "Agent Escalated"
    KNOWLEDGE_RETRIEVED = "Knowledge Retrieved"


@dataclass(slots=True)
class RuntimeEventMessage:
    id: UUID = field(default_factory=uuid4)
    name: RuntimeEventName = RuntimeEventName.TASK_STARTED
    organization_id: UUID | None = None
    task_id: UUID | None = None
    conversation_id: UUID | None = None
    agent_id: UUID | None = None
    payload_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus(Protocol):
    async def publish(self, event: RuntimeEventMessage) -> None: ...


class InMemoryEventBus:
    def __init__(self) -> None:
        self._events: list[RuntimeEventMessage] = []
        self._subscribers: list[Callable[[RuntimeEventMessage], None]] = []

    async def publish(self, event: RuntimeEventMessage) -> None:
        self._events.append(event)
        for subscriber in list(self._subscribers):
            subscriber(event)

    def subscribe(self, callback: Callable[[RuntimeEventMessage], None]) -> None:
        self._subscribers.append(callback)

    def list_events(self) -> list[RuntimeEventMessage]:
        return list(self._events)


class RedisEventBus:
    def __init__(self, redis_client, channel_prefix: str = "runtime:event") -> None:
        self.redis = redis_client
        self.channel_prefix = channel_prefix

    async def publish(self, event: RuntimeEventMessage) -> None:
        if self.redis is None:
            return
        channel = f"{self.channel_prefix}:{event.name.value}"
        payload = {
            "event_id": str(event.id),
            "event_name": event.name.value,
            "organization_id": str(event.organization_id) if event.organization_id else None,
            "task_id": str(event.task_id) if event.task_id else None,
            "conversation_id": str(event.conversation_id) if event.conversation_id else None,
            "agent_id": str(event.agent_id) if event.agent_id else None,
            "payload_json": event.payload_json,
            "created_at": event.created_at.isoformat(),
        }
        if hasattr(self.redis, "publish"):
            self.redis.publish(channel, payload)
