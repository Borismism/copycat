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
    gemini_location: str = "europe-west1"  # Vertex AI region (read from GEMINI_LOCATION env var)
    gemini_temperature: float = 0.2  # Low temp for consistency
    gemini_max_output_tokens: int = 40000  # Allow detailed responses (max is 65536)

    # Budget settings (in EUR)
    daily_budget_eur: float = 0.01  # €0.01 default (1 cent) - should be set via env var
    # NOTE: Gemini 2.5 Flash on Vertex AI uses Dynamic Shared Quota (DSQ)
    # No hard rate limits! Scales automatically based on availability

    # Token costs (per 1M tokens) - Vertex AI Gemini 2.5 Flash pricing (converted to EUR)
    # USD prices: $0.30 input, $2.50 output, $1.00 audio (converted at ~1.08)
    gemini_input_cost_per_1m: float = 0.28  # €0.28 per 1M input tokens
    gemini_output_cost_per_1m: float = 2.31  # €2.31 per 1M output tokens
    gemini_audio_cost_per_1m: float = 0.93  # €0.93 per 1M audio tokens

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
    firestore_database_id: str = "copycat"  # Matches terraform default
    firestore_videos_collection: str = "videos"
    firestore_budget_collection: str = "budget_tracking"

    # BigQuery
    bigquery_dataset: str = "copycat_dev"
    bigquery_results_table: str = "vision_analysis_results"

    # Logging
    log_level: str = "INFO"

    # Worker pool settings
    worker_pool_size: int = 10  # Number of concurrent video analysis workers


settings = Settings()
