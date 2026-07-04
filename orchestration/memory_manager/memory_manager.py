from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MemoryScope(str, Enum):
    SHORT_TERM = "short_term"
    CONVERSATION = "conversation"
    LONG_TERM = "long_term"
    ORGANIZATION = "organization"


@dataclass(slots=True)
class MemoryRecord:
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID | None = None
    conversation_id: UUID | None = None
    agent_id: UUID | None = None
    scope: MemoryScope = MemoryScope.SHORT_TERM
    content: str = ""
    metadata_json: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None


@dataclass(slots=True)
class MemoryRetrievalResult:
    records: list[MemoryRecord] = field(default_factory=list)
    compressed_context: str = ""
    metadata_json: dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    def __init__(self, redis_client=None, *, max_recent_records: int = 50) -> None:
        self.redis = redis_client
        self.max_recent_records = max_recent_records
        self._records: list[MemoryRecord] = []

    def remember(self, record: MemoryRecord) -> MemoryRecord:
        self._records.append(record)
        if self.redis is not None and hasattr(self.redis, "lpush"):
            self.redis.lpush(self._redis_key(record.organization_id, record.scope), json.dumps(self._serialize(record), default=str))
        self._prune_expired()
        return record

    def retrieve(
        self,
        *,
        organization_id: UUID | None = None,
        conversation_id: UUID | None = None,
        agent_id: UUID | None = None,
        scope: MemoryScope | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> MemoryRetrievalResult:
        self._prune_expired()
        candidates = [
            record
            for record in self._records
            if (organization_id is None or record.organization_id == organization_id)
            and (conversation_id is None or record.conversation_id == conversation_id)
            and (agent_id is None or record.agent_id == agent_id)
            and (scope is None or record.scope == scope)
        ]
        if query:
            scored = sorted(candidates, key=lambda record: self._score(query, record.content), reverse=True)
        else:
            scored = sorted(candidates, key=lambda record: record.created_at, reverse=True)
        selected = scored[:limit]
        return MemoryRetrievalResult(
            records=selected,
            compressed_context=self.compress_context(selected),
            metadata_json={"retrieved_count": len(selected), "scope": scope.value if scope else None},
        )

    def compress_context(self, records: list[MemoryRecord], *, max_characters: int = 4000) -> str:
        lines: list[str] = []
        total = 0
        for record in records:
            line = record.content.strip()
            if not line:
                continue
            if total + len(line) > max_characters:
                remaining = max_characters - total
                if remaining <= 0:
                    break
                line = line[:remaining]
            lines.append(line)
            total += len(line)
        return "\n".join(lines)

    def prune(self) -> None:
        self._prune_expired()
        self._records = self._records[-self.max_recent_records :]

    def _score(self, query: str, content: str) -> float:
        if not content:
            return 0.0
        query_terms = {token for token in query.lower().split() if token}
        content_terms = {token for token in content.lower().split() if token}
        if not query_terms or not content_terms:
            return 0.0
        overlap = len(query_terms & content_terms)
        return overlap / max(len(query_terms), 1)

    def _prune_expired(self) -> None:
        now = datetime.now(UTC)
        self._records = [record for record in self._records if record.expires_at is None or record.expires_at > now]

    def _redis_key(self, organization_id: UUID | None, scope: MemoryScope) -> str:
        return f"runtime:memory:{organization_id or 'global'}:{scope.value}"

    def _serialize(self, record: MemoryRecord) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "organization_id": str(record.organization_id) if record.organization_id else None,
            "conversation_id": str(record.conversation_id) if record.conversation_id else None,
            "agent_id": str(record.agent_id) if record.agent_id else None,
            "scope": record.scope.value,
            "content": record.content,
            "metadata_json": record.metadata_json,
            "importance": record.importance,
            "created_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }
