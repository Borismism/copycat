"""Configuration models for the Copycat system."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IntellectualProperty(BaseModel):
    """An intellectual property we're protecting."""

    id: str = Field(..., description="Unique identifier (e.g., 'superman', 'batman')")
    name: str = Field(..., description="Display name (e.g., 'Superman')")
    description: str = Field(..., description="Brief description of the IP")

    # Keywords for YouTube search
    search_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to search for on YouTube (e.g., ['superman ai', 'superman sora'])"
    )

    # Character names to detect in videos
    character_names: list[str] = Field(
        default_factory=list,
        description="Character names to look for (e.g., ['Superman', 'Clark Kent', 'Kal-El'])"
    )

    # Visual characteristics for detection
    visual_keywords: list[str] = Field(
        default_factory=list,
        description="Visual elements to detect (e.g., ['red cape', 'S symbol', 'blue suit'])"
    )

    # Risk weighting
    priority_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Priority multiplier for this IP (0.0-2.0)"
    )

    enabled: bool = Field(default=True, description="Whether to actively monitor this IP")


class CompanyInfo(BaseModel):
    """Information about the company we're protecting."""

    name: str = Field(..., description="Company name (e.g., 'Warner Bros. Entertainment')")
    description: str = Field(..., description="What the company does")
    protection_scope: str = Field(
        ...,
        description="What we're protecting (e.g., 'Justice League characters and related IP')"
    )

    # Contact/legal info
    legal_entity: Optional[str] = Field(None, description="Full legal entity name")
    jurisdiction: Optional[str] = Field(None, description="Primary jurisdiction (e.g., 'United States')")

    # Additional context
    notes: Optional[str] = Field(None, description="Additional context or notes")

    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = Field(default="system", description="Who last updated this config")


class SystemConfig(BaseModel):
    """Complete system configuration."""

    company: CompanyInfo
    intellectual_properties: list[IntellectualProperty]

    # System settings
    discovery_enabled: bool = Field(default=True, description="Enable discovery service")
    risk_analysis_enabled: bool = Field(default=True, description="Enable risk analyzer")
    vision_analysis_enabled: bool = Field(default=True, description="Enable vision analyzer")

    # Budget/limits
    daily_youtube_quota: int = Field(default=10000, description="Daily YouTube API quota limit")
    daily_gemini_budget_usd: float = Field(default=260.0, description="Daily Gemini budget in USD")

    version: int = Field(default=1, description="Config version for change tracking")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConfigUpdateRequest(BaseModel):
    """Natural language request to update configuration."""

    request: str = Field(..., description="What you want to change (natural language)")
    apply_immediately: bool = Field(
        default=False,
        description="Apply changes immediately (true) or return for review (false)"
    )


class ConfigUpdateResponse(BaseModel):
    """Response from config update request."""

    success: bool
    message: str

    # What would change
    proposed_changes: dict = Field(default_factory=dict)

    # Current vs new config
    current_config: Optional[SystemConfig] = None
    new_config: Optional[SystemConfig] = None

    # Applied or just proposed?
    applied: bool = Field(default=False)
