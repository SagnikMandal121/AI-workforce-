from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import jwt
from passlib.context import CryptContext

from backend.core.config import Settings
from backend.core.exceptions import TokenError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Role(str, Enum):
    OWNER = "Owner"
    ADMIN = "Admin"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"


class UserStatus(str, Enum):
    ACTIVE = "active"
    PENDING_VERIFICATION = "pending_verification"
    INVITED = "invited"
    SUSPENDED = "suspended"


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    INVITE = "invite"


ROLE_HIERARCHY = {
    Role.EMPLOYEE: 0,
    Role.MANAGER: 1,
    Role.ADMIN: 2,
    Role.OWNER: 3,
}


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    org_id: str
    email: str
    role: str
    token_type: str
    jti: str
    exp: int
    iat: int
    iss: str
    aud: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _build_claims(
    *,
    user_id: UUID,
    organization_id: UUID,
    email: str,
    role: Role,
    token_type: TokenType,
    settings: Settings,
    expires_delta: timedelta,
) -> dict[str, Any]:
    now = utcnow()
    exp = now + expires_delta
    jti = uuid4().hex
    return {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "email": email,
        "role": role.value,
        "token_type": token_type.value,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }


def create_token(
    *,
    user_id: UUID,
    organization_id: UUID,
    email: str,
    role: Role,
    token_type: TokenType,
    settings: Settings,
    expires_delta: timedelta,
) -> str:
    return jwt.encode(
        _build_claims(
            user_id=user_id,
            organization_id=organization_id,
            email=email,
            role=role,
            token_type=token_type,
            settings=settings,
            expires_delta=expires_delta,
        ),
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, settings: Settings, expected_type: TokenType | None = None) -> TokenPayload:
    try:
        decoded = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except jwt.PyJWTError as exc:
        raise TokenError() from exc

    if expected_type is not None and decoded.get("token_type") != expected_type.value:
        raise TokenError("Unexpected token type")

    return TokenPayload(**decoded)


def generate_secret_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def is_role_allowed(user_role: Role, required_role: Role) -> bool:
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required_role]
