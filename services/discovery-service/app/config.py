"""Configuration settings for the discovery service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service info
    service_name: str = "discovery-service"
    version: str = "0.1.0"
    port: int = 8080

    # GCP Configuration
    gcp_project_id: str = "copycat-429012"
    gcp_region: str = "europe-west4"
    environment: str = "development"

    # Firestore
    firestore_database_id: str = "(default)"

    # PubSub
    pubsub_topic_discovered_videos: str = "discovered-videos"
    pubsub_timeout_seconds: int = 60

    # YouTube API
    youtube_api_key: str = ""  # Loaded from Secret Manager via env var
    youtube_default_region: str = "US"

    # Discovery settings
    max_results_per_request: int = (
        50  # Optimized for quota efficiency (1 page = 100 units)
    )
    discovery_batch_size: int = 50

    # Logging
    log_level: str = "INFO"
    debug: bool = False


# Global settings instance
settings = Settings()
