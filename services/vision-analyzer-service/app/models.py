"""Pydantic models for vision analyzer service."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# Risk tiers from risk-analyzer-service
RiskTier = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "VERY_LOW"]


class VideoMetadata(BaseModel):
    """Video metadata from discovery/risk-analyzer."""

    video_id: str
    youtube_url: str
    title: str
    duration_seconds: int
    view_count: int
    channel_id: str
    channel_title: str
    risk_score: float = Field(..., ge=0, le=100)
    risk_tier: RiskTier
    matched_characters: list[str] = Field(default_factory=list)
    matched_ips: list[str] = Field(
        default_factory=list
    )  # IP config IDs - REQUIRED from discovery-service
    discovered_at: datetime
    last_risk_update: datetime


class ScanReadyMessage(BaseModel):
    """PubSub message from scan-ready topic."""

    video_id: str
    priority: int  # Higher = more urgent
    metadata: VideoMetadata


class CharacterDetection(BaseModel):
    """Detected character in video."""

    name: str
    screen_time_seconds: int
    prominence: str  # Allow any string, we'll validate in prompt
    timestamps: list[str]  # Format: "MM:SS-MM:SS"
    description: str


class AIGeneratedAnalysis(BaseModel):
    """AI-generated content detection."""

    is_ai: bool
    confidence: float = Field(..., ge=0, le=100)
    tools_detected: list[str] = Field(default_factory=list)
    evidence: str


class FairUseFactors(BaseModel):
    """Fair use doctrine analysis."""

    purpose: str  # Suggested: commercial, educational, commentary, transformative
    purpose_explanation: str
    nature: str  # Suggested: creative_work, factual
    amount_used: str  # Suggested: substantial, minimal
    amount_explanation: str
    market_effect: str  # Suggested: high, medium, low
    market_explanation: str


class CopyrightAssessment(BaseModel):
    """Copyright infringement assessment."""

    infringement_likelihood: float = Field(..., ge=0, le=100)
    reasoning: str
    fair_use_applies: bool
    fair_use_factors: FairUseFactors


class VideoCharacteristics(BaseModel):
    """Video content characteristics."""

    duration_category: Literal["short", "medium", "long", "full_length"]
    content_type: Literal["full_movie", "trailer", "clips", "review", "other"]
    monetization_detected: bool
    professional_quality: bool


class IPCharacterDetection(BaseModel):
    """Character detection for multi-IP format."""
    name: str
    screen_time_seconds: float
    prominence: Literal["primary", "secondary", "background"]
    timestamps: list[str]
    description: str


class IPAnalysisResult(BaseModel):
    """Analysis result for a single IP config."""
    ip_id: str
    ip_name: str
    contains_infringement: bool
    characters_detected: list[IPCharacterDetection] = []
    is_ai_generated: bool = False
    ai_tools_detected: list[str] = []
    fair_use_applies: bool = False
    fair_use_reasoning: str = ""
    content_type: str = "other"  # Accept any content type string from Gemini
    infringement_likelihood: float = Field(0, ge=0, le=100)
    reasoning: str = ""  # Optional - Gemini might forget this
    recommended_action: str = "monitor"  # Accept any action string from Gemini


class GeminiAnalysisResult(BaseModel):
    """Structured output from Gemini analysis (multi-IP format)."""

    ip_results: list[IPAnalysisResult]
    overall_recommendation: str  # Accept any recommendation string from Gemini
    overall_notes: str


class AnalysisMetrics(BaseModel):
    """Cost and performance metrics."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    processing_time_seconds: float
    frames_analyzed: int
    fps_used: float


class IPSpecificResult(BaseModel):
    """Analysis result for a specific IP (for multi-IP videos)."""

    ip_id: str
    ip_name: str
    contains_infringement: bool
    characters_detected: list[CharacterDetection]
    infringement_likelihood: float = Field(..., ge=0, le=100)
    reasoning: str
    recommended_action: Literal["immediate_takedown", "monitor", "safe_harbor", "ignore"]


class VisionAnalysisResult(BaseModel):
    """Complete analysis result with metadata."""

    video_id: str
    analyzed_at: datetime
    gemini_model: str
    analysis: GeminiAnalysisResult
    metrics: AnalysisMetrics
    config_used: dict[str, Any]  # VideoConfig as dict
    matched_ips: list[str] = Field(default_factory=list)  # IPs this video was analyzed against
    ip_specific_results: list[IPSpecificResult] = Field(
        default_factory=list
    )  # Results per IP (for multi-IP videos)


class FeedbackMessage(BaseModel):
    """Feedback message to risk-analyzer for learning."""

    video_id: str
    channel_id: str
    contains_infringement: bool
    confidence_score: float
    infringement_type: str
    characters_found: list[str]
    analysis_cost_usd: float
    analyzed_at: datetime
