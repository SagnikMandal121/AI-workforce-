from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from backend.database.schemas.knowledge import SearchRequest, SearchResponse, SearchChunkRead
from backend.services.knowledge_service import KnowledgeService


@dataclass(slots=True)
class KnowledgeCitation:
    document_id: UUID
    chunk_id: UUID
    knowledge_base_id: UUID | None = None
    title: str | None = None
    source_uri: str | None = None
    score: float = 0.0
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KnowledgeContext:
    query: str
    results: list[SearchChunkRead] = field(default_factory=list)
    citations: list[KnowledgeCitation] = field(default_factory=list)
    compressed_context: str = ""
    metadata_json: dict[str, Any] = field(default_factory=dict)


class KnowledgeManager(Protocol):
    def retrieve(self, *, current_user, request: SearchRequest, actor_user_id: UUID | None = None) -> KnowledgeContext: ...


class RuntimeKnowledgeManager:
    def __init__(self, knowledge_service: KnowledgeService | None) -> None:
        self.knowledge_service = knowledge_service

    def retrieve(self, *, current_user, request: SearchRequest, actor_user_id: UUID | None = None) -> KnowledgeContext:
        if self.knowledge_service is None:
            return KnowledgeContext(query=request.query, metadata_json={"available": False})
        response = self.knowledge_service.semantic_search(current_user, request, actor_user_id=actor_user_id)
        citations = [
            KnowledgeCitation(
                document_id=item.document.id,
                chunk_id=item.chunk.id,
                knowledge_base_id=item.document.knowledge_base_id,
                title=item.document.title,
                source_uri=item.document.source_uri,
                score=item.similarity_score,
                metadata_json=item.source_reference,
            )
            for item in response.results
        ]
        return KnowledgeContext(
            query=response.query,
            results=response.results,
            citations=citations,
            compressed_context="\n".join(item.chunk.chunk_text for item in response.results),
            metadata_json={"search_type": response.search_type, "cache_hit": response.cache_hit, "top_k": response.top_k},
        )
