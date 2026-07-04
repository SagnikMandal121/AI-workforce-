from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from backend.database.models.knowledge import (
    Document,
    DocumentChunk,
    DocumentVersion,
    Embedding,
    KnowledgeBase,
    RetrievalLog,
)
from backend.database.repositories.base import BaseRepository


class KnowledgeBaseRepository(BaseRepository):
    def create(self, knowledge_base: KnowledgeBase) -> KnowledgeBase:
        self.session.add(knowledge_base)
        self.session.flush()
        return knowledge_base

    def get_by_id(self, knowledge_base_id: UUID) -> KnowledgeBase | None:
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_organization(self, organization_id: UUID) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.organization_id == organization_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())


class DocumentRepository(BaseRepository):
    def create(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        return document

    def get_by_id(self, document_id: UUID) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.versions), selectinload(Document.chunks))
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_document_key(self, knowledge_base_id: UUID, document_key: str) -> Document | None:
        stmt = select(Document).where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.document_key == document_key,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_knowledge_base(self, knowledge_base_id: UUID, include_deleted: bool = False) -> list[Document]:
        stmt = select(Document).where(Document.knowledge_base_id == knowledge_base_id)
        if not include_deleted:
            stmt = stmt.where(Document.is_deleted.is_(False))
        stmt = stmt.order_by(Document.created_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def soft_delete(self, document: Document) -> None:
        document.is_deleted = True
        self.session.flush()


class DocumentVersionRepository(BaseRepository):
    def create(self, version: DocumentVersion) -> DocumentVersion:
        self.session.add(version)
        self.session.flush()
        return version

    def list_by_document(self, document_id: UUID) -> list[DocumentVersion]:
        stmt = select(DocumentVersion).where(DocumentVersion.document_id == document_id).order_by(
            DocumentVersion.version_number.desc()
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_current(self, document_id: UUID) -> DocumentVersion | None:
        stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.is_current.is_(True),
        )
        return self.session.execute(stmt).scalar_one_or_none()


class DocumentChunkRepository(BaseRepository):
    def bulk_create(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        self.session.add_all(chunks)
        self.session.flush()
        return chunks

    def list_by_version(self, version_id: UUID) -> list[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.version_id == version_id).order_by(DocumentChunk.chunk_index)
        return list(self.session.execute(stmt).scalars().all())

    def list_by_document(self, document_id: UUID) -> list[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
        return list(self.session.execute(stmt).scalars().all())

    def delete_by_version(self, version_id: UUID) -> None:
        self.session.execute(delete(DocumentChunk).where(DocumentChunk.version_id == version_id))

    def delete_by_document(self, document_id: UUID) -> None:
        self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))


class EmbeddingRepository(BaseRepository):
    def upsert(self, embedding: Embedding) -> Embedding:
        existing = self.get_by_chunk_id(embedding.chunk_id)
        if existing is None:
            self.session.add(embedding)
            self.session.flush()
            return embedding

        existing.provider_name = embedding.provider_name
        existing.model_name = embedding.model_name
        existing.dimensions = embedding.dimensions
        existing.vector = embedding.vector
        existing.checksum = embedding.checksum
        existing.metadata_json = embedding.metadata_json
        existing.deleted_at = embedding.deleted_at
        self.session.flush()
        return existing

    def get_by_chunk_id(self, chunk_id: UUID) -> Embedding | None:
        stmt = select(Embedding).where(Embedding.chunk_id == chunk_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_document(self, document_id: UUID) -> list[Embedding]:
        stmt = select(Embedding).where(Embedding.document_id == document_id)
        return list(self.session.execute(stmt).scalars().all())

    def delete_by_document(self, document_id: UUID) -> None:
        self.session.execute(delete(Embedding).where(Embedding.document_id == document_id))

    def delete_by_version(self, version_id: UUID) -> None:
        chunk_ids = select(DocumentChunk.id).where(DocumentChunk.version_id == version_id)
        self.session.execute(delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids)))


class RetrievalLogRepository(BaseRepository):
    def create(self, log: RetrievalLog) -> RetrievalLog:
        self.session.add(log)
        self.session.flush()
        return log

    def list_by_organization(self, organization_id: UUID, limit: int = 100) -> list[RetrievalLog]:
        stmt = (
            select(RetrievalLog)
            .where(RetrievalLog.organization_id == organization_id)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())