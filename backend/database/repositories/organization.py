from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.organization import Organization
from backend.database.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository):
    def get_by_id(self, organization_id: UUID) -> Organization | None:
        return self.session.get(Organization, organization_id)

    def get_by_domain(self, domain: str) -> Organization | None:
        stmt = select(Organization).where(Organization.domain == domain)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, organization: Organization) -> Organization:
        self.session.add(organization)
        self.session.flush()
        return organization

    def delete(self, organization: Organization) -> None:
        self.session.delete(organization)
