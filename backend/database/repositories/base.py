from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session


class BaseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session


class TenantScopedRepository(BaseRepository):
    def __init__(self, session: Session, organization_id: UUID | None = None) -> None:
        super().__init__(session)
        self.organization_id = organization_id
