"""Configuration settings for API service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # GCP settings
    gcp_project_id: str
    gcp_region: str = "us-central1"
    environment: str = "dev"

    # Service URLs (set by Terraform via remote state)
    discovery_service_url: str | None = None

    # Firestore settings
    firestore_emulator_host: str | None = None
    firestore_database: str = "(default)"  # Database name (default for emulator, copycat-{env} for GCP)

    # BigQuery settings
    bigquery_dataset: str = "copycat_dev"


settings = Settings()
