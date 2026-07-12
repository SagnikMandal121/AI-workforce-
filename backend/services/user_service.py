from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictError, NotFoundError, ValidationError
from backend.core.security import Role, UserStatus, generate_secret_token, hash_password, verify_password
from database.models.user import User
from database.repositories.user import UserRepository
from database.schemas.auth import InviteUserRequest


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = UserRepository(session)

    def get_current(self, user_id: UUID, organization_id: UUID) -> User:
        user = self.repository.get_by_id(user_id, organization_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def list_by_organization(self, organization_id: UUID) -> list[User]:
        return self.repository.list_by_organization(organization_id)

    def update_current(self, user: User, first_name: str | None = None, last_name: str | None = None) -> User:
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        self.session.commit()
        return user

    def invite_user(
        self,
        *,
        inviter_role: Role,
        organization_id: UUID,
        payload: InviteUserRequest,
    ) -> User:
        existing = self.repository.get_by_email(payload.email)
        if existing is not None:
            raise ConflictError("A user with this email already exists")

        if inviter_role is Role.ADMIN and payload.role in {Role.ADMIN, Role.OWNER}:
            raise ValidationError("Admins cannot invite admins")
        if inviter_role is Role.MANAGER:
            raise ValidationError("Managers cannot invite users")
        if inviter_role is Role.EMPLOYEE:
            raise ValidationError("Employees cannot invite users")

        invited_user = User(
            organization_id=organization_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password_hash=hash_password(generate_secret_token()),
            role=payload.role,
            status=UserStatus.INVITED,
        )
        self.repository.create(invited_user)
        return invited_user

    def activate_invited_user(self, *, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        user.status = UserStatus.ACTIVE
        self.session.flush()
        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise ValidationError("Current password is invalid")
        user.password_hash = hash_password(new_password)
        self.session.flush()
        return user
