from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from uuid import UUID

from backend.core.deps import get_current_user, get_knowledge_service, require_min_role
from backend.core.security import Role
from database.models.knowledge import DocumentSourceType
from database.schemas.auth import AuthMessageResponse
from database.schemas.knowledge import (
    DocumentListResponse,
    DocumentRead,
    DocumentUploadCreate,
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseRead,
    KnowledgeHealthResponse,
    KnowledgeOperationResponse,
    KnowledgeSearchResultResponse,
    SearchRequest,
    SearchResponse,
)
from backend.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge-base"])


@router.get("", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(
    current_user=Depends(get_current_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.list_knowledge_bases(current_user)


@router.get("/health", response_model=KnowledgeHealthResponse)
def health(
    current_user=Depends(get_current_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.get_health(current_user)


@router.post("/bases", response_model=KnowledgeBaseRead)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user=Depends(require_min_role(Role.ADMIN)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.create_knowledge_base(current_user, payload)


@router.get("/bases/{knowledge_base_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    knowledge_base_id: UUID,
    current_user=Depends(get_current_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.get_knowledge_base(current_user, knowledge_base_id)


@router.get("/bases/{knowledge_base_id}/documents", response_model=DocumentListResponse)
def list_documents(
    knowledge_base_id: UUID,
    current_user=Depends(get_current_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.list_documents(current_user, knowledge_base_id)


@router.post("/bases/{knowledge_base_id}/documents", response_model=DocumentRead)
def upload_document(
    knowledge_base_id: UUID,
    payload: DocumentUploadCreate,
    current_user=Depends(require_min_role(Role.EMPLOYEE)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    result = knowledge_service.upload_document(current_user, knowledge_base_id, payload)
    return result.document


@router.post("/bases/{knowledge_base_id}/documents/upload", response_model=DocumentRead)
async def upload_document_file(
    knowledge_base_id: UUID,
    file: UploadFile = File(...),
    source_type: DocumentSourceType = DocumentSourceType.TXT,
    title: str | None = None,
    source_uri: str | None = None,
    mime_type: str | None = None,
    process_inline: bool = True,
    current_user=Depends(require_min_role(Role.EMPLOYEE)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    payload = DocumentUploadCreate(
        title=title or file.filename,
        source_type=source_type,
        source_uri=source_uri,
        file_name=file.filename,
        mime_type=mime_type or file.content_type,
        content_text=(await file.read()).decode("utf-8", errors="ignore"),
        process_inline=process_inline,
    )
    result = knowledge_service.upload_document(current_user, knowledge_base_id, payload)
    return result.document


@router.delete("/documents/{document_id}", response_model=KnowledgeOperationResponse)
def delete_document(
    document_id: UUID,
    current_user=Depends(require_min_role(Role.ADMIN)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.delete_document(current_user, document_id)


@router.post("/documents/{document_id}/reindex", response_model=DocumentRead)
def reindex_document(
    document_id: UUID,
    current_user=Depends(require_min_role(Role.EMPLOYEE)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    result = knowledge_service.reindex_document(current_user, document_id)
    return result.document


@router.post("/search/semantic", response_model=SearchResponse)
def semantic_search(
    payload: SearchRequest,
    current_user=Depends(get_current_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.semantic_search(current_user, payload)


@router.post("/search/hybrid", response_model=SearchResponse)
def hybrid_search(
    payload: SearchRequest,
    current_user=Depends(get_current_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.hybrid_search(current_user, payload)


@router.post("/search/top-k", response_model=KnowledgeSearchResultResponse)
def retrieve_top_k(
    payload: SearchRequest,
    current_user=Depends(get_current_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    return knowledge_service.retrieve_top_k(current_user, payload)
