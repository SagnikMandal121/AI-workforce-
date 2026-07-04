from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.security import Role, is_role_allowed
from backend.database.models.organization import Organization
from backend.database.repositories.organization import OrganizationRepository
from backend.database.schemas.organization import OrganizationUpdate


class OrganizationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = OrganizationRepository(session)

    def get_current(self, organization_id: UUID) -> Organization:
        organization = self.repository.get_by_id(organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization

    def update_current(self, organization_id: UUID, payload: OrganizationUpdate) -> Organization:
        organization = self.get_current(organization_id)
        updates = payload.model_dump(exclude_unset=True)
        if "domain" in updates and updates["domain"]:
            existing = self.repository.get_by_domain(updates["domain"])
            if existing and existing.organization_id != organization.organization_id:
                raise ValidationError("An organization with this domain already exists")
        for key, value in updates.items():
            setattr(organization, key, value)
        self.session.flush()
        self.session.commit()
        return organization

    def delete_workspace(self, organization_id: UUID, role: Role) -> None:
        if role is not Role.OWNER:
            raise ValidationError("Only owners can delete the workspace")
        organization = self.get_current(organization_id)
        self.repository.delete(organization)
        self.session.commit()

    def assert_can_manage_billing(self, role: Role) -> None:
        if role is not Role.OWNER:
            raise ValidationError("Only owners can manage billing")

    def assert_can_invite_admin(self, role: Role) -> None:
        if role is not Role.OWNER:
            raise ValidationError("Only owners can invite admins")

    def assert_can_invite_users(self, role: Role) -> None:
        if not is_role_allowed(role, Role.ADMIN):
            raise ValidationError("Only admins or owners can invite users")

    def assert_can_view_analytics(self, role: Role) -> None:
        if not is_role_allowed(role, Role.MANAGER):
            raise ValidationError("Only managers, admins, or owners can view analytics")

    def assert_can_view_assigned_agents(self, role: Role) -> None:
        if not is_role_allowed(role, Role.EMPLOYEE):
            raise ValidationError("Unauthorized")
