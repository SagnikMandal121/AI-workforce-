import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    app_name: str = "AI Workforce Runtime"
    version: str = "0.1.0"
    
    # Database Settings
    postgres_url: str = os.getenv("POSTGRES_URL", "postgresql+asyncpg://user:password@localhost:5432/ai_workforce")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # LLM Settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

settings = Settings()
