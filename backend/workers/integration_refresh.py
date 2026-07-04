from __future__ import annotations

from backend.core.config import get_settings
from backend.database.session import get_redis_client, get_session
from backend.services.integration_service import IntegrationService


def run_integration_token_refresh(limit: int = 100) -> int:
    settings = get_settings()
    session = next(get_session())
    try:
        service = IntegrationService(session=session, settings=settings, redis_client=get_redis_client())
        refreshed = service.refresh_due_tokens(limit=limit)
        session.commit()
        return refreshed
    finally:
        session.close()