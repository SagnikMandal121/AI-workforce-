from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from database.models.knowledge import DocumentSourceType, KnowledgeBaseStatus
from database.schemas.common import TimestampedSchema


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class KnowledgeBaseRead(TimestampedSchema):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None = None
    status: KnowledgeBaseStatus
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    deleted_at: datetime | None = None
    document_count: int = 0
    version_count: int = 0
    chunk_count: int = 0


class DocumentUploadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    source_type: DocumentSourceType
    source_uri: str | None = Field(default=None, max_length=2048)
    file_name: str | None = Field(default=None, max_length=512)
    mime_type: str | None = Field(default=None, max_length=255)
    content_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    parser_metadata: dict[str, Any] = Field(default_factory=dict)
    process_inline: bool = True

    @field_validator("title", "source_uri", "file_name", "mime_type")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class DocumentVersionRead(BaseModel):
    id: UUID
    document_id: UUID
    knowledge_base_id: UUID
    version_number: int
    source_type: DocumentSourceType
    source_uri: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    parser_name: str
    parser_metadata: dict[str, Any] = Field(default_factory=dict)
    chunk_strategy: str
    chunk_count: int
    checksum: str
    is_current: bool
    indexed_at: datetime | None = None
    deleted_at: datetime | None = None
    extracted_text: str
    cleaned_text: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DocumentChunkRead(BaseModel):
    id: UUID
    document_id: UUID
    version_id: UUID
    knowledge_base_id: UUID
    chunk_index: int
    page_number: int | None = None
    heading: str | None = None
    chunk_text: str
    token_count: int
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    checksum: str
    created_at: datetime


class DocumentEmbeddingRead(BaseModel):
    id: UUID
    chunk_id: UUID
    provider_name: str
    model_name: str
    dimensions: int
    vector: list[float]
    checksum: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DocumentRead(BaseModel):
    id: UUID
    knowledge_base_id: UUID
    organization_id: UUID
    document_key: str
    title: str
    source_type: DocumentSourceType
    source_uri: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    checksum: str
    latest_version_number: int
    is_deleted: bool
    deleted_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    current_version: DocumentVersionRead | None = None
    versions: list[DocumentVersionRead] = Field(default_factory=list)
    chunks: list[DocumentChunkRead] = Field(default_factory=list)
    embeddings: list[DocumentEmbeddingRead] = Field(default_factory=list)


class RetrievalFilters(BaseModel):
    knowledge_base_id: UUID | None = None
    document_id: UUID | None = None
    source_type: DocumentSourceType | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=50)
    knowledge_base_id: UUID | None = None
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    search_type: str = Field(default="semantic", max_length=64)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        return value.strip()


class SearchChunkRead(BaseModel):
    chunk: DocumentChunkRead
    document: DocumentRead
    similarity_score: float
    source_reference: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    search_type: str
    top_k: int
    cache_hit: bool
    results: list[SearchChunkRead]
    retrieved_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeOperationResponse(BaseModel):
    message: str


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseRead]


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]


class RetrievalLogRead(BaseModel):
    id: UUID
    organization_id: UUID
    knowledge_base_id: UUID | None = None
    document_id: UUID | None = None
    query_text: str
    search_type: str
    top_k: int
    result_count: int
    filters_json: dict[str, Any]
    result_chunk_ids: list[str]
    similarity_scores: list[float]
    cache_hit: bool
    latency_ms: int
    actor_user_id: UUID | None = None
    request_id: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class KnowledgeSearchResultResponse(BaseModel):
    knowledge_base_id: UUID | None = None
    results: list[SearchChunkRead]
    top_k: int
    cache_hit: bool


class KnowledgeHealthResponse(BaseModel):
    status: str
    knowledge_bases: int
    documents: int
    chunks: int
    embeddings: int