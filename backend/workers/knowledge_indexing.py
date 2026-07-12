from __future__ import annotations

from backend.core.config import get_settings
from database.session import get_redis_client, get_session
from backend.services.knowledge_service import KnowledgeService


def run_knowledge_indexing(limit: int = 100) -> int:
    settings = get_settings()
    session = next(get_session())
    try:
        service = KnowledgeService(session=session, settings=settings, redis_client=get_redis_client())
        processed = service.process_background_jobs(limit=limit)
        session.commit()
        return processed
    finally:
        session.close()
