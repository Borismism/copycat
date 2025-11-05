"""Configuration for vision-analyzer service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service metadata
    service_name: str = "vision-analyzer-service"
    version: str = "0.1.0"
    environment: str = "dev"

    # GCP settings
    gcp_project_id: str
    gcp_region: str = "europe-west4"

    # Gemini settings
    gemini_model: str = "gemini-2.5-flash"  # Latest model with video support
    gemini_location: str = "europe-west4"  # Vertex AI region
    gemini_temperature: float = 0.2  # Low temp for consistency
    gemini_max_output_tokens: int = 40000  # Allow detailed responses (max is 65536)

    # Budget settings (in USD)
    daily_budget_usd: float = 260.0  # €240 ≈ $260
    # NOTE: Gemini 2.5 Flash on Vertex AI uses Dynamic Shared Quota (DSQ)
    # No hard rate limits! Scales automatically based on availability

    # Token costs (per 1M tokens) - Vertex AI Gemini 2.5 Flash pricing
    gemini_input_cost_per_1m: float = 0.30  # $0.30 per 1M input tokens
    gemini_output_cost_per_1m: float = 2.50  # $2.50 per 1M output tokens
    gemini_audio_cost_per_1m: float = 1.00  # $1.00 per 1M audio tokens

    # Video processing costs (tokens per second at low resolution)
    # At 1 FPS: 66 tokens/frame + 32 tokens/second audio = 98 tokens/second
    # Gemini docs say ~100 tokens/second at low res
    tokens_per_second_low_res: int = 100  # Total: 66 frames + 32 audio + overhead
    tokens_per_frame_low_res: int = 66
    tokens_per_second_audio: int = 32

    # PubSub topics
    pubsub_scan_ready_topic: str = "scan-ready"
    pubsub_scan_ready_subscription: str = "scan-ready-vision-analyzer-sub"
    pubsub_feedback_topic: str = "vision-feedback"

    # Firestore
    firestore_videos_collection: str = "videos"
    firestore_budget_collection: str = "budget_tracking"

    # BigQuery
    bigquery_dataset: str = "copycat_dev"
    bigquery_results_table: str = "vision_analysis_results"

    # Logging
    log_level: str = "INFO"


settings = Settings()
