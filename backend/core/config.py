from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Workforce"
    environment: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"

    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_workforce"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me"
    integration_encryption_key: str = "change-me-integration-encryption-key"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "ai-workforce"
    jwt_audience: str = "ai-workforce-users"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    email_verification_expire_hours: int = 24
    password_reset_expire_minutes: int = 30
    integration_oauth_state_expire_minutes: int = 10
    integration_refresh_window_minutes: int = 15
    integration_refresh_lock_seconds: int = 60

    knowledge_embedding_provider: str = "deterministic"
    knowledge_embedding_model: str = "deterministic-embeddings"
    knowledge_embedding_dimensions: int = 256
    knowledge_chunk_size: int = 1200
    knowledge_chunk_overlap: int = 200
    knowledge_search_cache_ttl_seconds: int = 300
    knowledge_reindex_batch_size: int = 50

    openapi_url: str = "/openapi.json"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"

    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
