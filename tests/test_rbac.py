from __future__ import annotations

import pytest

from backend.core.exceptions import ValidationError
from backend.core.security import Role
from backend.database.models.organization import Organization
from backend.database.models.user import User
from backend.database.schemas.auth import InviteUserRequest
from backend.services.organization_service import OrganizationService
from backend.services.user_service import UserService


def test_owner_can_manage_billing_and_delete_workspace(db_session):
    service = OrganizationService(db_session)
    service.assert_can_manage_billing(Role.OWNER)
    service.assert_can_invite_admin(Role.OWNER)


def test_admin_cannot_invite_admin(db_session):
    org = Organization(company_name="Org A", timezone="UTC", subscription="trial")
    db_session.add(org)
    db_session.commit()

    user_service = UserService(db_session)
    with pytest.raises(ValidationError):
        user_service.invite_user(
            inviter_role=Role.ADMIN,
            organization_id=org.organization_id,
            payload=InviteUserRequest(
                email="invitee@example.com",
                first_name="Invitee",
                last_name="User",
                role=Role.ADMIN,
            ),
        )
