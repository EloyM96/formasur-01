"""Application configuration module."""
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Centralised application settings."""

    environment: str = "development"
    database_url: str = "sqlite:///./prl_notifier.db"
    queue_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
