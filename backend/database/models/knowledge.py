from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from backend.database.base import Base
from backend.database.models.common import TimeStampedMixin, UUIDMixin


class KnowledgeBaseStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class DocumentSourceType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    CSV = "csv"
    WEBSITE_URL = "website_url"
    NOTION = "notion"
    GOOGLE_DRIVE = "google_drive"
    CONFLUENCE = "confluence"


class KnowledgeVector(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        return [float(item) for item in value]

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        return [float(item) for item in value]


class KnowledgeBase(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_knowledge_bases_organization_name"),
        Index("ix_knowledge_bases_organization_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        SAEnum(
            KnowledgeBaseStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=KnowledgeBaseStatus.ACTIVE,
        nullable=False,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    retrieval_logs = relationship("RetrievalLog", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "document_key", name="uq_documents_knowledge_base_key"),
        Index("ix_documents_organization_knowledge_base", "organization_id", "knowledge_base_id"),
        Index("ix_documents_checksum", "organization_id", "checksum"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    document_key: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[DocumentSourceType] = mapped_column(
        SAEnum(
            DocumentSourceType,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    source_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    latest_version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentVersion.document_id",
    )
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
        Index("ix_document_versions_checksum", "organization_id", "checksum"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[DocumentSourceType] = mapped_column(
        SAEnum(
            DocumentSourceType,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    source_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    parser_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    chunk_strategy: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    document = relationship("Document", back_populates="versions", foreign_keys=[document_id])
    chunks = relationship("DocumentChunk", back_populates="version", cascade="all, delete-orphan")


class DocumentChunk(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index", name="uq_document_chunks_version_index"),
        Index("ix_document_chunks_organization_knowledge_base", "organization_id", "knowledge_base_id"),
        Index("ix_document_chunks_version_index", "version_id", "chunk_index"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="chunks")
    version = relationship("DocumentVersion", back_populates="chunks")
    embedding = relationship(
        "Embedding",
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Embedding(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_embeddings_chunk"),
        Index("ix_embeddings_organization_knowledge_base", "organization_id", "knowledge_base_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[list[float]] = mapped_column(KnowledgeVector(256), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunk = relationship("DocumentChunk", back_populates="embedding")


class RetrievalLog(Base, UUIDMixin, TimeStampedMixin):
    __tablename__ = "retrieval_logs"
    __table_args__ = (
        Index("ix_retrieval_logs_organization_created_at", "organization_id", "created_at"),
        Index("ix_retrieval_logs_knowledge_base_created_at", "knowledge_base_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_type: Mapped[str] = mapped_column(String(64), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    similarity_scores: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    knowledge_base = relationship("KnowledgeBase", back_populates="retrieval_logs")