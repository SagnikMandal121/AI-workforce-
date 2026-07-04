from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.core.config import Settings
from backend.core.exceptions import ConflictError, NotFoundError, ValidationError
from backend.core.security import utcnow
from backend.database.models.knowledge import (
    Document,
    DocumentChunk,
    DocumentSourceType,
    DocumentVersion,
    Embedding,
    KnowledgeBase,
    KnowledgeBaseStatus,
    RetrievalLog,
)
from backend.database.models.user import User
from backend.database.repositories.knowledge import (
    DocumentChunkRepository,
    DocumentRepository,
    DocumentVersionRepository,
    EmbeddingRepository,
    KnowledgeBaseRepository,
    RetrievalLogRepository,
)
from backend.database.schemas.knowledge import (
    DocumentChunkRead,
    DocumentEmbeddingRead,
    DocumentListResponse,
    DocumentRead,
    DocumentUploadCreate,
    DocumentVersionRead,
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseRead,
    KnowledgeHealthResponse,
    KnowledgeOperationResponse,
    KnowledgeSearchResultResponse,
    SearchChunkRead,
    SearchRequest,
    SearchResponse,
)
from backend.services.knowledge.chunking import ChunkResult, RecursiveChunker
from backend.services.knowledge.parsers import ParsedDocument, ParserRegistry
from backend.services.knowledge.providers import EmbeddingProviderRegistry
from backend.services.knowledge.search import cosine_similarity, lexical_similarity


@dataclass(slots=True)
class IngestionResult:
    document: DocumentRead
    version: DocumentVersionRead
    chunks: list[DocumentChunkRead]


class KnowledgeService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        redis_client: Redis | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.redis = redis_client
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.documents = DocumentRepository(session)
        self.versions = DocumentVersionRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.embeddings = EmbeddingRepository(session)
        self.logs = RetrievalLogRepository(session)
        self.parser_registry = ParserRegistry()
        self.chunker = RecursiveChunker()
        self.embedding_registry = EmbeddingProviderRegistry(settings.knowledge_embedding_dimensions)

    def create_knowledge_base(self, current_user: User, payload: KnowledgeBaseCreate) -> KnowledgeBaseRead:
        existing = self._get_knowledge_base_by_name(current_user.organization_id, payload.name)
        if existing is not None and existing.deleted_at is None:
            raise ConflictError("A knowledge base with this name already exists")

        knowledge_base = existing or KnowledgeBase(
            organization_id=current_user.organization_id,
            name=payload.name,
            description=payload.description,
            status=KnowledgeBaseStatus.ACTIVE,
            metadata_json=payload.metadata,
        )
        if existing is None:
            self.knowledge_bases.create(knowledge_base)
        else:
            knowledge_base.description = payload.description
            knowledge_base.status = KnowledgeBaseStatus.ACTIVE
            knowledge_base.deleted_at = None
            knowledge_base.metadata_json = payload.metadata

        self.session.commit()
        return self._serialize_knowledge_base(knowledge_base)

    def list_knowledge_bases(self, current_user: User) -> KnowledgeBaseListResponse:
        knowledge_bases = self.knowledge_bases.list_by_organization(current_user.organization_id)
        return KnowledgeBaseListResponse(items=[self._serialize_knowledge_base(item) for item in knowledge_bases])

    def get_knowledge_base(self, current_user: User, knowledge_base_id: UUID) -> KnowledgeBaseRead:
        knowledge_base = self._get_knowledge_base(current_user.organization_id, knowledge_base_id)
        return self._serialize_knowledge_base(knowledge_base)

    def upload_document(
        self,
        current_user: User,
        knowledge_base_id: UUID,
        payload: DocumentUploadCreate,
        raw_bytes: bytes | None = None,
        *,
        request_id: str | None = None,
    ) -> IngestionResult:
        knowledge_base = self._get_knowledge_base(current_user.organization_id, knowledge_base_id)
        if knowledge_base.deleted_at is not None:
            raise ValidationError("Knowledge base is not active")

        parser = self.parser_registry.get(payload.source_type)
        parsed = parser.parse(
            raw_bytes=raw_bytes,
            content_text=payload.content_text,
            source_uri=payload.source_uri,
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            metadata=payload.parser_metadata,
        )
        cleaned_text = parsed.text.strip()
        if not cleaned_text:
            raise ValidationError("Document content is empty")

        document_key = self._build_document_key(payload)
        content_hash = self._build_checksum(cleaned_text, payload.source_type.value, payload.source_uri or "", payload.file_name or "")
        existing = self.documents.get_by_document_key(knowledge_base.id, document_key)

        if existing is not None and existing.checksum == content_hash and not existing.is_deleted:
            return IngestionResult(
                document=self._serialize_document(existing),
                version=self._serialize_version(self._current_version(existing)),
                chunks=self._serialize_chunks(existing.chunks),
            )

        if existing is None:
            document = Document(
                organization_id=current_user.organization_id,
                knowledge_base_id=knowledge_base.id,
                document_key=document_key,
                title=payload.title or parsed.title or document_key,
                source_type=payload.source_type,
                source_uri=payload.source_uri,
                file_name=payload.file_name,
                mime_type=payload.mime_type,
                checksum=content_hash,
                latest_version_number=1,
                is_deleted=False,
                deleted_at=None,
                metadata_json=payload.metadata,
            )
            self.documents.create(document)
        else:
            document = existing
            document.is_deleted = False
            document.deleted_at = None
            document.checksum = content_hash
            document.title = payload.title or parsed.title or document.title
            document.source_type = payload.source_type
            document.source_uri = payload.source_uri
            document.file_name = payload.file_name
            document.mime_type = payload.mime_type
            document.metadata_json = payload.metadata
            document.latest_version_number += 1

        version_number = document.latest_version_number
        version = DocumentVersion(
            organization_id=current_user.organization_id,
            knowledge_base_id=knowledge_base.id,
            document_id=document.id,
            version_number=version_number,
            source_type=payload.source_type,
            source_uri=payload.source_uri,
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            extracted_text=parsed.text,
            cleaned_text=cleaned_text,
            parser_name=parser.__class__.__name__,
            parser_metadata={**parsed.metadata, **payload.parser_metadata},
            chunk_strategy=self.chunker.name,
            checksum=content_hash,
            is_current=True,
            indexed_at=None,
            metadata_json=payload.metadata,
        )
        for previous_version in self.versions.list_by_document(document.id):
            previous_version.is_current = False
        self.versions.create(version)
        document.current_version_id = version.id

        self._log_event(
            organization_id=current_user.organization_id,
            knowledge_base_id=knowledge_base.id,
            document_id=document.id,
            action="upload",
            metadata={"file_name": payload.file_name, "source_type": payload.source_type.value, "request_id": request_id},
        )

        if payload.process_inline:
            self._process_version(current_user, document, version)
        else:
            self._enqueue_index_job(version.id)
            self.session.commit()

        return IngestionResult(
            document=self._serialize_document(document),
            version=self._serialize_version(version),
            chunks=self._serialize_chunks(self.chunks.list_by_version(version.id)),
        )

    def list_documents(self, current_user: User, knowledge_base_id: UUID) -> DocumentListResponse:
        knowledge_base = self._get_knowledge_base(current_user.organization_id, knowledge_base_id)
        documents = self.documents.list_by_knowledge_base(knowledge_base.id)
        return DocumentListResponse(items=[self._serialize_document(document) for document in documents])

    def delete_document(self, current_user: User, document_id: UUID) -> KnowledgeOperationResponse:
        document = self._get_document(current_user.organization_id, document_id)
        document.is_deleted = True
        document.deleted_at = utcnow()
        for version in self.versions.list_by_document(document.id):
            version.deleted_at = utcnow()
            version.is_current = False
        for chunk in self.chunks.list_by_document(document.id):
            chunk.deleted_at = utcnow()
            if chunk.embedding is not None:
                chunk.embedding.deleted_at = utcnow()
        self._log_event(
            organization_id=current_user.organization_id,
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            action="delete",
            metadata={"document_id": str(document.id)},
        )
        self.session.commit()
        return KnowledgeOperationResponse(message="Document deleted successfully")

    def reindex_document(self, current_user: User, document_id: UUID) -> IngestionResult:
        document = self._get_document(current_user.organization_id, document_id)
        version = self._current_version(document)
        if version is None:
            raise NotFoundError("Document version not found")
        self._process_version(current_user, document, version, reset_embeddings=True)
        return IngestionResult(
            document=self._serialize_document(document),
            version=self._serialize_version(version),
            chunks=self._serialize_chunks(self.chunks.list_by_version(version.id)),
        )

    def semantic_search(self, current_user: User, payload: SearchRequest, *, actor_user_id: UUID | None = None) -> SearchResponse:
        return self._search(current_user, payload, search_type="semantic", actor_user_id=actor_user_id)

    def hybrid_search(self, current_user: User, payload: SearchRequest, *, actor_user_id: UUID | None = None) -> SearchResponse:
        return self._search(current_user, payload, search_type="hybrid", actor_user_id=actor_user_id)

    def retrieve_top_k(self, current_user: User, payload: SearchRequest, *, actor_user_id: UUID | None = None) -> KnowledgeSearchResultResponse:
        response = self.semantic_search(current_user, payload, actor_user_id=actor_user_id)
        return KnowledgeSearchResultResponse(
            knowledge_base_id=payload.knowledge_base_id,
            results=response.results,
            top_k=response.top_k,
            cache_hit=response.cache_hit,
        )

    def get_health(self, current_user: User) -> KnowledgeHealthResponse:
        knowledge_bases = self.knowledge_bases.list_by_organization(current_user.organization_id)
        stmt = (
            select(
                func.count(func.distinct(Document.id)),
                func.count(func.distinct(DocumentVersion.id)),
                func.count(func.distinct(DocumentChunk.id)),
                func.count(func.distinct(Embedding.id)),
            )
            .select_from(Document)
            .join(KnowledgeBase, KnowledgeBase.id == Document.knowledge_base_id)
            .outerjoin(DocumentVersion, DocumentVersion.document_id == Document.id)
            .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
            .outerjoin(Embedding, Embedding.document_id == Document.id)
            .where(KnowledgeBase.organization_id == current_user.organization_id)
        )
        documents, versions, chunks, embeddings = self.session.execute(stmt).one()
        return KnowledgeHealthResponse(
            status="ok",
            knowledge_bases=len(knowledge_bases),
            documents=int(documents or 0),
            chunks=int(chunks or 0),
            embeddings=int(embeddings or 0),
        )

    def ingest_pending_version(self, version_id: UUID) -> None:
        version = self.session.get(DocumentVersion, version_id)
        if version is None or version.deleted_at is not None:
            return
        document = self._get_document(version.organization_id, version.document_id)
        self._process_version(None, document, version, reset_embeddings=True)

    def process_background_jobs(self, limit: int = 100) -> int:
        if self.redis is None:
            return 0
        processed = 0
        queue_key = self._queue_key()
        while processed < limit:
            raw = self.redis.rpop(queue_key)
            if raw is None:
                break
            payload = json.loads(raw)
            self.ingest_pending_version(UUID(payload["version_id"]))
            self.session.commit()
            processed += 1
        return processed

    def _process_version(
        self,
        current_user: User | None,
        document: Document,
        version: DocumentVersion,
        *,
        reset_embeddings: bool = False,
    ) -> None:
        if reset_embeddings:
            self.embeddings.delete_by_version(version.id)
            self.chunks.delete_by_version(version.id)

        chunks = self.chunker.chunk(
            version.cleaned_text,
            chunk_size=self.settings.knowledge_chunk_size,
            chunk_overlap=self.settings.knowledge_chunk_overlap,
        )
        created_chunks = self._create_chunks(document, version, chunks)
        embeddings = self._embed_chunks(document, version, created_chunks)
        version.chunk_count = len(created_chunks)
        version.is_current = True
        version.indexed_at = utcnow()
        document.current_version_id = version.id
        document.latest_version_number = max(document.latest_version_number, version.version_number)
        self._log_event(
            organization_id=document.organization_id,
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            action="reindex" if reset_embeddings else "ingest",
            metadata={"version_id": str(version.id), "chunk_count": len(created_chunks)},
        )
        self._cache_invalidate(document.organization_id)
        self.session.commit()

    def _create_chunks(
        self,
        document: Document,
        version: DocumentVersion,
        chunks: list[ChunkResult],
    ) -> list[DocumentChunk]:
        created: list[DocumentChunk] = []
        for item in chunks:
            created.append(
                DocumentChunk(
                    organization_id=document.organization_id,
                    knowledge_base_id=document.knowledge_base_id,
                    document_id=document.id,
                    version_id=version.id,
                    chunk_index=item.chunk_index,
                    page_number=item.page_number,
                    heading=item.heading,
                    chunk_text=item.chunk_text,
                    token_count=item.token_count,
                    metadata_json={**item.metadata, "version": version.version_number, "file_name": version.file_name},
                    checksum=item.checksum,
                )
            )
        return self.chunks.bulk_create(created)

    def _embed_chunks(
        self,
        document: Document,
        version: DocumentVersion,
        chunks: list[DocumentChunk],
    ) -> list[Embedding]:
        provider = self.embedding_registry.get(self.settings.knowledge_embedding_provider)
        texts = [chunk.chunk_text for chunk in chunks]
        embeddings = provider.embed_texts(texts)
        created: list[Embedding] = []
        for chunk, vector in zip(chunks, embeddings, strict=True):
            created.append(
                self.embeddings.upsert(
                    Embedding(
                        organization_id=document.organization_id,
                        knowledge_base_id=document.knowledge_base_id,
                        document_id=document.id,
                        chunk_id=chunk.id,
                        provider_name=provider.provider_name,
                        model_name=provider.model_name,
                        dimensions=len(vector),
                        vector=vector,
                        checksum=hashlib.sha256((chunk.checksum + provider.model_name).encode("utf-8")).hexdigest(),
                        metadata_json={"version": version.version_number, "chunk_index": chunk.chunk_index},
                    )
                )
            )
        return created

    def _search(self, current_user: User, payload: SearchRequest, *, search_type: str, actor_user_id: UUID | None = None) -> SearchResponse:
        cache_key = self._cache_key(current_user.organization_id, search_type, payload)
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached_response = SearchResponse.model_validate(cached)
            cached_response.cache_hit = True
            return cached_response

        start = time.perf_counter()
        query_vector = self.embedding_registry.get(self.settings.knowledge_embedding_provider).embed_query(payload.query)
        query = (
            select(Embedding, DocumentChunk, Document, DocumentVersion, KnowledgeBase)
            .join(DocumentChunk, DocumentChunk.id == Embedding.chunk_id)
            .join(Document, Document.id == Embedding.document_id)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.version_id)
            .join(KnowledgeBase, KnowledgeBase.id == Embedding.knowledge_base_id)
            .where(
                KnowledgeBase.organization_id == current_user.organization_id,
                KnowledgeBase.deleted_at.is_(None),
                Document.is_deleted.is_(False),
                DocumentChunk.deleted_at.is_(None),
                Embedding.deleted_at.is_(None),
                DocumentVersion.deleted_at.is_(None),
            )
        )
        if payload.knowledge_base_id is not None:
            query = query.where(Embedding.knowledge_base_id == payload.knowledge_base_id)
        if payload.filters.document_id is not None:
            query = query.where(Embedding.document_id == payload.filters.document_id)
        if payload.filters.source_type is not None:
            query = query.where(Document.source_type == payload.filters.source_type)

        rows = list(self.session.execute(query).all())
        scored: list[tuple[float, Embedding, DocumentChunk, Document, DocumentVersion, KnowledgeBase]] = []
        for embedding, chunk, document, version, knowledge_base in rows:
            vector_score = cosine_similarity(query_vector, embedding.vector)
            lexical_score = lexical_similarity(payload.query, chunk.chunk_text)
            score = vector_score if search_type == "semantic" else (0.8 * vector_score + 0.2 * lexical_score)
            scored.append((score, embedding, chunk, document, version, knowledge_base))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[: payload.top_k]
        results = [self._serialize_search_result(score, embedding, chunk, document, version, knowledge_base) for score, embedding, chunk, document, version, knowledge_base in selected]
        latency_ms = int((time.perf_counter() - start) * 1000)
        response = SearchResponse(
            query=payload.query,
            search_type=search_type,
            top_k=payload.top_k,
            cache_hit=False,
            results=results,
            retrieved_count=len(results),
            metadata={"latency_ms": latency_ms},
        )
        self._log_event(
            organization_id=current_user.organization_id,
            knowledge_base_id=payload.knowledge_base_id,
            action="search",
            metadata={
                "query": payload.query,
                "search_type": search_type,
                "top_k": payload.top_k,
                "result_count": len(results),
                "latency_ms": latency_ms,
                "cache_hit": False,
            },
        )
        self._cache_set(cache_key, response.model_dump())
        return response

    def _serialize_knowledge_base(self, knowledge_base: KnowledgeBase) -> KnowledgeBaseRead:
        documents = self.documents.list_by_knowledge_base(knowledge_base.id, include_deleted=True)
        version_count = 0
        chunk_count = 0
        for document in documents:
            version_count += len(document.versions)
            chunk_count += len(document.chunks)
        return KnowledgeBaseRead(
            id=knowledge_base.id,
            organization_id=knowledge_base.organization_id,
            name=knowledge_base.name,
            description=knowledge_base.description,
            status=knowledge_base.status,
            metadata_json=knowledge_base.metadata_json,
            deleted_at=knowledge_base.deleted_at,
            created_at=knowledge_base.created_at,
            updated_at=knowledge_base.updated_at,
            document_count=len(documents),
            version_count=version_count,
            chunk_count=chunk_count,
        )

    def _serialize_document(self, document: Document) -> DocumentRead:
        current_version = self._current_version(document)
        versions = self.versions.list_by_document(document.id)
        chunks = self.chunks.list_by_document(document.id)
        embeddings = self.embeddings.list_by_document(document.id)
        return DocumentRead(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            organization_id=document.organization_id,
            document_key=document.document_key,
            title=document.title,
            source_type=document.source_type,
            source_uri=document.source_uri,
            file_name=document.file_name,
            mime_type=document.mime_type,
            checksum=document.checksum,
            latest_version_number=document.latest_version_number,
            is_deleted=document.is_deleted,
            deleted_at=document.deleted_at,
            metadata_json=document.metadata_json,
            current_version=self._serialize_version(current_version) if current_version else None,
            versions=[self._serialize_version(item) for item in versions],
            chunks=self._serialize_chunks(chunks),
            embeddings=[self._serialize_embedding(item) for item in embeddings],
        )

    def _serialize_version(self, version: DocumentVersion | None) -> DocumentVersionRead:
        if version is None:
            raise NotFoundError("Document version not found")
        return DocumentVersionRead(
            id=version.id,
            document_id=version.document_id,
            knowledge_base_id=version.knowledge_base_id,
            version_number=version.version_number,
            source_type=version.source_type,
            source_uri=version.source_uri,
            file_name=version.file_name,
            mime_type=version.mime_type,
            parser_name=version.parser_name,
            parser_metadata=version.parser_metadata,
            chunk_strategy=version.chunk_strategy,
            chunk_count=version.chunk_count,
            checksum=version.checksum,
            is_current=version.is_current,
            indexed_at=version.indexed_at,
            deleted_at=version.deleted_at,
            extracted_text=version.extracted_text,
            cleaned_text=version.cleaned_text,
            metadata_json=version.metadata_json,
        )

    def _serialize_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunkRead]:
        return [
            DocumentChunkRead(
                id=chunk.id,
                document_id=chunk.document_id,
                version_id=chunk.version_id,
                knowledge_base_id=chunk.knowledge_base_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                heading=chunk.heading,
                chunk_text=chunk.chunk_text,
                token_count=chunk.token_count,
                metadata_json=chunk.metadata_json,
                checksum=chunk.checksum,
                created_at=chunk.created_at,
            )
            for chunk in chunks
        ]

    def _serialize_embedding(self, embedding: Embedding) -> DocumentEmbeddingRead:
        return DocumentEmbeddingRead(
            id=embedding.id,
            chunk_id=embedding.chunk_id,
            provider_name=embedding.provider_name,
            model_name=embedding.model_name,
            dimensions=embedding.dimensions,
            vector=embedding.vector,
            checksum=embedding.checksum,
            metadata_json=embedding.metadata_json,
        )

    def _serialize_search_result(
        self,
        score: float,
        embedding: Embedding,
        chunk: DocumentChunk,
        document: Document,
        version: DocumentVersion,
        knowledge_base: KnowledgeBase,
    ) -> SearchChunkRead:
        document_read = self._serialize_document(document)
        chunk_read = self._serialize_chunks([chunk])[0]
        source_reference = {
            "knowledge_base_id": str(knowledge_base.id),
            "knowledge_base_name": knowledge_base.name,
            "document_id": str(document.id),
            "document_title": document.title,
            "file_name": document.file_name,
            "source_uri": document.source_uri,
            "page_number": chunk.page_number,
            "heading": chunk.heading,
            "version": version.version_number,
        }
        return SearchChunkRead(
            chunk=chunk_read,
            document=document_read,
            similarity_score=round(score, 6),
            source_reference=source_reference,
        )

    def _current_version(self, document: Document) -> DocumentVersion | None:
        if document.current_version_id is None:
            versions = self.versions.list_by_document(document.id)
            return versions[0] if versions else None
        return self.session.get(DocumentVersion, document.current_version_id)

    def _get_knowledge_base(self, organization_id: UUID, knowledge_base_id: UUID) -> KnowledgeBase:
        knowledge_base = self.knowledge_bases.get_by_id(knowledge_base_id)
        if knowledge_base is None or knowledge_base.organization_id != organization_id:
            raise NotFoundError("Knowledge base not found")
        return knowledge_base

    def _get_knowledge_base_by_name(self, organization_id: UUID, name: str) -> KnowledgeBase | None:
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.organization_id == organization_id,
            KnowledgeBase.name == name,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def _get_document(self, organization_id: UUID, document_id: UUID) -> Document:
        document = self.documents.get_by_id(document_id)
        if document is None or document.organization_id != organization_id:
            raise NotFoundError("Document not found")
        return document

    def _build_document_key(self, payload: DocumentUploadCreate) -> str:
        source_key = payload.source_uri or payload.file_name or payload.title or payload.content_text or uuid4().hex
        return hashlib.sha256(f"{payload.source_type.value}:{source_key}".encode("utf-8")).hexdigest()

    def _build_checksum(self, text: str, *parts: str) -> str:
        digest = hashlib.sha256()
        digest.update(text.encode("utf-8"))
        for part in parts:
            digest.update(part.encode("utf-8"))
        return digest.hexdigest()

    def _log_event(
        self,
        *,
        organization_id: UUID,
        action: str,
        knowledge_base_id: UUID | None = None,
        document_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RetrievalLog:
        log = RetrievalLog(
            organization_id=organization_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            query_text=metadata.get("query", action) if metadata else action,
            search_type=action,
            top_k=int(metadata.get("top_k", 0)) if metadata else 0,
            result_count=int(metadata.get("result_count", 0)) if metadata else 0,
            filters_json=metadata or {},
            result_chunk_ids=[],
            similarity_scores=[],
            cache_hit=bool(metadata.get("cache_hit", False)) if metadata else False,
            latency_ms=int(metadata.get("latency_ms", 0)) if metadata else 0,
            actor_user_id=None,
            request_id=metadata.get("request_id") if metadata else None,
            metadata_json=metadata or {},
        )
        return self.logs.create(log)

    def _enqueue_index_job(self, version_id: UUID) -> None:
        if self.redis is None:
            return
        self.redis.lpush(self._queue_key(), json.dumps({"version_id": str(version_id)}))

    def _queue_key(self) -> str:
        return "knowledge:index:queue"

    def _cache_key(self, organization_id: UUID, search_type: str, payload: SearchRequest) -> str:
        digest = hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()
        return f"knowledge:search:{organization_id}:{search_type}:{digest}"

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        if self.redis is None:
            return None
        raw = self.redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        if self.redis is None:
            return
        self.redis.setex(key, self.settings.knowledge_search_cache_ttl_seconds, json.dumps(value, default=str))

    def _cache_invalidate(self, organization_id: UUID) -> None:
        if self.redis is None:
            return
        pattern = f"knowledge:search:{organization_id}:*"
        if hasattr(self.redis, "scan_iter"):
            for key in list(self.redis.scan_iter(match=pattern)):
                self.redis.delete(key)
            return
        for key in list(getattr(self.redis, "store", {}).keys()):
            if key.startswith(f"knowledge:search:{organization_id}:"):
                self.redis.delete(key)

