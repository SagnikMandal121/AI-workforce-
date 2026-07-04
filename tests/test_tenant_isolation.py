from __future__ import annotations

from backend.core.security import Role, UserStatus
from backend.database.models.organization import Organization
from backend.database.models.user import User
from backend.database.repositories.user import UserRepository
from backend.services.organization_service import OrganizationService
from backend.services.user_service import UserService


def test_repository_scopes_users_by_organization(db_session):
    org_a = Organization(company_name="Org A", timezone="UTC", subscription="trial")
    org_b = Organization(company_name="Org B", timezone="UTC", subscription="trial")
    db_session.add_all([org_a, org_b])
    db_session.flush()

    user = User(
        organization_id=org_a.organization_id,
        first_name="Alice",
        last_name="Example",
        email="alice@example.com",
        password_hash="hash",
        role=Role.EMPLOYEE,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()

    repo = UserRepository(db_session)
    assert repo.get_by_id(user.id, org_a.organization_id) is not None
    assert repo.get_by_id(user.id, org_b.organization_id) is None


def test_organization_delete_is_scoped(db_session):
    org = Organization(company_name="Org A", timezone="UTC", subscription="trial")
    db_session.add(org)
    db_session.commit()

    service = OrganizationService(db_session)
    service.delete_workspace(org.organization_id, Role.OWNER)
    assert service.repository.get_by_id(org.organization_id) is None
