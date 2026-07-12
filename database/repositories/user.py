from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.security import Role, UserStatus
from database.models.user import User
from database.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def get_by_id(self, user_id: UUID, organization_id: UUID) -> User | None:
        stmt = select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower().strip())
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_organization(self, organization_id: UUID) -> list[User]:
        stmt = select(User).where(User.organization_id == organization_id).order_by(User.created_at.asc())
        return list(self.session.execute(stmt).scalars().all())

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def update_status(self, user: User, status: UserStatus) -> User:
        user.status = status
        self.session.flush()
        return user

    def update_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        self.session.flush()
        return user

    def update_role(self, user: User, role: Role) -> User:
        user.role = role
        self.session.flush()
        return user
