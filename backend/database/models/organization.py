from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from backend.database.base import Base
from backend.database.models.common import TimeStampedMixin


class Organization(Base, TimeStampedMixin):
    __tablename__ = "organizations"

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    subscription: Mapped[str] = mapped_column(String(64), default="trial", nullable=False)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
