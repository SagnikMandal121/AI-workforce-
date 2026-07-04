from __future__ import annotations

import json
import time
from datetime import timedelta
from uuid import UUID

from redis import Redis

from backend.core.config import Settings
from backend.core.exceptions import TokenError
from backend.core.security import Role, TokenPayload, TokenType, create_token, decode_token


class TokenService:
    def __init__(self, settings: Settings, redis_client: Redis) -> None:
        self.settings = settings
        self.redis = redis_client

    def _ttl_seconds(self, exp_ts: int) -> int:
        ttl = exp_ts - int(time.time())
        return max(ttl, 1)

    def issue_access_token(self, *, user_id: UUID, organization_id: UUID, email: str, role: Role) -> str:
        return create_token(
            user_id=user_id,
            organization_id=organization_id,
            email=email,
            role=role,
            token_type=TokenType.ACCESS,
            settings=self.settings,
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
        )

    def issue_refresh_token(self, *, user_id: UUID, organization_id: UUID, email: str, role: Role) -> str:
        return create_token(
            user_id=user_id,
            organization_id=organization_id,
            email=email,
            role=role,
            token_type=TokenType.REFRESH,
            settings=self.settings,
            expires_delta=timedelta(days=self.settings.refresh_token_expire_days),
        )

    def issue_one_time_token(
        self,
        *,
        token_type: TokenType,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        role: Role,
        expires_delta: timedelta,
    ) -> str:
        token = create_token(
            user_id=user_id,
            organization_id=organization_id,
            email=email,
            role=role,
            token_type=token_type,
            settings=self.settings,
            expires_delta=expires_delta,
        )
        payload = decode_token(token, self.settings, expected_type=token_type)
        self.redis.setex(
            self._one_time_key(token_type, payload.jti),
            self._ttl_seconds(payload.exp),
            json.dumps(payload.__dict__),
        )
        return token

    def store_refresh_session(self, refresh_token: str) -> TokenPayload:
        payload = decode_token(refresh_token, self.settings, expected_type=TokenType.REFRESH)
        self.redis.setex(
            self._refresh_key(payload.jti),
            self._ttl_seconds(payload.exp),
            json.dumps(payload.__dict__),
        )
        return payload

    def get_refresh_session(self, refresh_token: str) -> TokenPayload:
        payload = decode_token(refresh_token, self.settings, expected_type=TokenType.REFRESH)
        value = self.redis.get(self._refresh_key(payload.jti))
        if value is None:
            raise TokenError("Refresh token has been revoked")
        return payload

    def revoke_refresh_token(self, refresh_token: str) -> None:
        payload = decode_token(refresh_token, self.settings, expected_type=TokenType.REFRESH)
        self.redis.delete(self._refresh_key(payload.jti))

    def revoke_access_token(self, access_token: str) -> None:
        payload = decode_token(access_token, self.settings, expected_type=TokenType.ACCESS)
        self.redis.setex(
            self._access_blacklist_key(payload.jti),
            self._ttl_seconds(payload.exp),
            "1",
        )

    def is_access_token_revoked(self, access_token: str) -> bool:
        payload = decode_token(access_token, self.settings, expected_type=TokenType.ACCESS)
        return self.redis.exists(self._access_blacklist_key(payload.jti)) == 1

    def consume_one_time_token(self, token: str, token_type: TokenType) -> TokenPayload:
        payload = decode_token(token, self.settings, expected_type=token_type)
        key = self._one_time_key(token_type, payload.jti)
        value = self.redis.get(key)
        if value is None:
            raise TokenError("Token has expired or was already used")
        self.redis.delete(key)
        return payload

    def _refresh_key(self, jti: str) -> str:
        return f"refresh:{jti}"

    def _access_blacklist_key(self, jti: str) -> str:
        return f"access:blacklist:{jti}"

    def _one_time_key(self, token_type: TokenType, jti: str) -> str:
        return f"one-time:{token_type.value}:{jti}"
