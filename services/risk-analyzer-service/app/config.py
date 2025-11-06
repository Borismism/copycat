"""Configuration settings for the risk-analyzer service."""

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
    service_name: str = "risk-analyzer-service"
    version: str = "0.1.0"
    port: int = 8080

    # GCP Configuration
    gcp_project_id: str = "copycat-429012"
    gcp_region: str = "europe-west4"
    environment: str = "development"

    # Firestore
    firestore_database_id: str = "copycat"  # Matches terraform default

    # PubSub
    pubsub_subscription_video_discovered: str = "risk-analyzer-video-discovered-sub"
    pubsub_subscription_vision_feedback: str = "risk-analyzer-vision-feedback-sub"
    pubsub_timeout_seconds: int = 60

    # Risk analysis settings
    rescan_batch_size: int = 100
    analysis_interval_seconds: int = 3600  # Run every hour

    # Risk tier scan frequencies (seconds)
    scan_frequency_critical: int = 6 * 3600  # 6 hours
    scan_frequency_high: int = 24 * 3600  # 24 hours
    scan_frequency_medium: int = 72 * 3600  # 72 hours
    scan_frequency_low: int = 7 * 24 * 3600  # 7 days
    scan_frequency_very_low: int = 30 * 24 * 3600  # 30 days

    # Logging
    log_level: str = "INFO"
    debug: bool = False


# Global settings instance
settings = Settings()
