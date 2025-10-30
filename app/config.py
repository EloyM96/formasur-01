"""Application configuration module."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application settings sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"

    # External SQL bridge (optional)
    external_sql_enabled: bool = False
    external_sql_database_url: str | None = None
    external_sql_echo: bool = False

    # Redis / Queue
    redis_url: str = "redis://localhost:6379/0"
    queue_url: str = "redis://localhost:6379/0"

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str | None = None

    # Moodle integration
    moodle_api_enabled: bool = False
    moodle_token: str | None = None
    moodle_rest_base_url: str | None = None
    moodle_soap_wsdl_url: str | None = None

    # Prevengos integration
    prevengos_csv_path: str = "data/prevengos/training_status.csv"
    prevengos_api_base_url: str | None = None
    prevengos_api_token: str | None = None
    prevengos_db_dsn: str | None = None


settings = Settings()
