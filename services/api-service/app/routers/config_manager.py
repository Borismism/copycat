"""Configuration management endpoint with Gemini-powered natural language updates."""

import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from google import genai
from google.auth import default

from app.core.auth import get_current_user, require_role
from app.core.firestore_client import firestore_client
from app.models import UserInfo, UserRole
from app.models.config import (
    CompanyInfo,
    ConfigUpdateRequest,
    ConfigUpdateResponse,
    IntellectualProperty,
    SystemConfig,
)
from app.utils.logging_utils import log_exception_json

router = APIRouter()
logger = logging.getLogger(__name__)

# Gemini client (lazy init)
_gemini_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Get or create Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        _credentials, project = default()
        _gemini_client = genai.Client(
            vertexai=True,
            project=project,
            location=os.getenv("GEMINI_LOCATION", "europe-west1")
        )
    return _gemini_client


def load_system_config() -> SystemConfig:
    """Load system config from Firestore."""
    try:
        doc_ref = firestore_client.db.collection("system_config").document("main")
        doc = doc_ref.get()

        if not doc.exists:
            # Return default config if none exists
            return get_default_config()

        data = doc.to_dict()
        return SystemConfig(**data)

    except Exception as e:
        log_exception_json(logger, "Failed to load system config", e, severity="ERROR")
        raise HTTPException(status_code=500, detail="Failed to load configuration")


def save_system_config(config: SystemConfig) -> bool:
    """Save system config to Firestore."""
    try:
        config.updated_at = datetime.utcnow()
        config.version += 1

        doc_ref = firestore_client.db.collection("system_config").document("main")
        doc_ref.set(config.model_dump(mode='json'), merge=False)

        logger.info(f"Saved system config version {config.version}")
        return True

    except Exception as e:
        log_exception_json(logger, "Failed to save system config", e, severity="ERROR")
        return False


def get_default_config() -> SystemConfig:
    """Get default Warner Bros / Justice League configuration."""
    return SystemConfig(
        company=CompanyInfo(
            name="Warner Bros. Entertainment",
            description="American film and entertainment studio",
            protection_scope="Justice League characters and related intellectual property",
            legal_entity="Warner Bros. Entertainment Inc.",
            jurisdiction="United States",
            notes="Protecting DC Comics Justice League franchise from AI-generated copyright infringement"
        ),
        intellectual_properties=[
            IntellectualProperty(
                id="superman",
                name="Superman",
                description="Kryptonian superhero, member of Justice League",
                search_keywords=["superman ai", "superman sora", "superman ai generated", "clark kent ai"],
                character_names=["Superman", "Clark Kent", "Kal-El", "Man of Steel"],
                visual_keywords=["red cape", "S symbol", "blue suit", "red boots"],
                priority_weight=1.5,
                enabled=True
            ),
            IntellectualProperty(
                id="batman",
                name="Batman",
                description="Dark Knight, billionaire vigilante",
                search_keywords=["batman ai", "batman sora", "bruce wayne ai", "dark knight ai"],
                character_names=["Batman", "Bruce Wayne", "Dark Knight", "Caped Crusader"],
                visual_keywords=["bat symbol", "black cape", "cowl", "batsuit"],
                priority_weight=1.5,
                enabled=True
            ),
            IntellectualProperty(
                id="wonder_woman",
                name="Wonder Woman",
                description="Amazon warrior princess",
                search_keywords=["wonder woman ai", "diana prince ai", "wonder woman sora"],
                character_names=["Wonder Woman", "Diana Prince", "Diana of Themyscira"],
                visual_keywords=["lasso of truth", "tiara", "bracelets", "star-spangled costume"],
                priority_weight=1.3,
                enabled=True
            ),
            IntellectualProperty(
                id="flash",
                name="The Flash",
                description="Fastest man alive, speedster hero",
                search_keywords=["flash ai", "barry allen ai", "flash sora", "speedster ai"],
                character_names=["The Flash", "Barry Allen", "Flash", "Scarlet Speedster"],
                visual_keywords=["red suit", "lightning bolt", "speed force", "yellow boots"],
                priority_weight=1.2,
                enabled=True
            ),
            IntellectualProperty(
                id="aquaman",
                name="Aquaman",
                description="King of Atlantis, ocean hero",
                search_keywords=["aquaman ai", "arthur curry ai", "aquaman sora"],
                character_names=["Aquaman", "Arthur Curry", "King of Atlantis"],
                visual_keywords=["trident", "orange armor", "atlantean", "underwater"],
                priority_weight=1.1,
                enabled=True
            ),
            IntellectualProperty(
                id="cyborg",
                name="Cyborg",
                description="Half-human, half-machine hero",
                search_keywords=["cyborg ai", "victor stone ai", "cyborg sora"],
                character_names=["Cyborg", "Victor Stone", "Vic Stone"],
                visual_keywords=["cybernetic", "metal body", "glowing eye", "tech suit"],
                priority_weight=1.0,
                enabled=True
            ),
            IntellectualProperty(
                id="green_lantern",
                name="Green Lantern",
                description="Intergalactic peace officer with power ring",
                search_keywords=["green lantern ai", "hal jordan ai", "green lantern sora"],
                character_names=["Green Lantern", "Hal Jordan", "John Stewart"],
                visual_keywords=["power ring", "green suit", "green light", "lantern symbol"],
                priority_weight=1.0,
                enabled=True
            ),
        ],
        discovery_enabled=True,
        risk_analysis_enabled=True,
        vision_analysis_enabled=True,
        daily_youtube_quota=10000,
        daily_gemini_budget_usd=260.0,
        version=1
    )


@router.get("", response_model=SystemConfig)
async def get_config():
    """
    Get current system configuration.

    Returns the active configuration including:
    - Company information
    - Intellectual properties being protected
    - System settings and limits
    """
    return load_system_config()


@router.post("/initialize")
@require_role(UserRole.ADMIN)
async def initialize_config(user: UserInfo = Depends(get_current_user)):
    """
    Initialize configuration with Warner Bros / Justice League defaults.

    Use this to set up the system for the first time or reset to defaults.

    Requires: ADMIN role only
    """
    try:
        default_config = get_default_config()
        success = save_system_config(default_config)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save config")

        return {
            "success": True,
            "message": "Configuration initialized with Warner Bros / Justice League defaults",
            "config": default_config
        }

    except Exception as e:
        log_exception_json(logger, "Failed to initialize config", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update", response_model=ConfigUpdateResponse)
@require_role(UserRole.ADMIN, UserRole.EDITOR)
async def update_config_natural_language(request: ConfigUpdateRequest, user: UserInfo = Depends(get_current_user)):
    """
    Update configuration using natural language.

    Uses Gemini AI to parse your request and generate configuration changes.

    Examples:
    - "Add Mickey Mouse to the intellectual properties we're protecting"
    - "Change the daily Gemini budget to $500"
    - "Disable vision analysis"
    - "Add search keywords 'superman runway' and 'superman fashion' to Superman"

    Set apply_immediately=true to apply changes, or false to review first.

    Requires: EDITOR or ADMIN role
    """
    try:
        # Load current config
        current_config = load_system_config()

        # Build Gemini prompt
        prompt = f"""
You are a configuration assistant for the Copycat copyright detection system.

Current configuration:
```json
{current_config.model_dump_json(indent=2)}
```

User request: "{request.request}"

Your task:
1. Understand what the user wants to change
2. Generate the new configuration with those changes applied
3. Explain what changed

Respond in JSON format:
{{
  "changes_summary": "Brief description of what changed",
  "new_config": <full SystemConfig object with changes applied>,
  "warnings": ["Any potential issues or suggestions"]
}}

## CRITICAL RULES FOR SEARCH KEYWORDS GENERATION

When generating `search_keywords` for intellectual properties, you MUST follow this pattern:

### Pattern 1: Character + AI Tool Combinations
For EACH character, generate keywords combining the character name with ALL major AI video tools:
- {{character}} ai
- {{character}} sora
- {{character}} runway
- {{character}} kling
- {{character}} pika
- {{character}} luma
- {{character}} veo
- {{character}} veo3
- {{character}} minimax
- {{character}} gen-2
- {{character}} gen-3
- {{character}} ai generated
- {{character}} ai movie
- {{character}} ai video

**Example for Superman:**
- "superman ai"
- "superman sora"
- "superman runway"
- "superman kling"
- "superman pika"
- "superman luma"
- "superman veo"
- "superman veo3"
- "superman minimax"
- "superman gen-2"
- "superman ai generated"
- "superman ai movie"

### Pattern 2: Franchise/Property + AI Tools
For movies, games, franchises, or other major properties, use the same pattern:
- {{property}} ai
- {{property}} sora
- {{property}} runway
- {{property}} kling
- {{property}} veo3
- {{property}} ai movie
- {{property}} ai trailer

**Example for Harry Potter:**
- "harry potter ai"
- "harry potter sora"
- "harry potter runway"
- "harry potter veo3"
- "harry potter ai movie"
- "hogwarts ai"
- "hogwarts sora"
- "quidditch ai"

### Pattern 3: Important Locations/Objects + AI
For iconic locations, vehicles, or objects from the IP:
- {{location}} ai
- {{vehicle}} ai
- {{object}} ai

**Example for DC Universe:**
- "batmobile ai"
- "gotham city ai"
- "fortress of solitude ai"
- "daily planet ai"

### Pattern 4: Alternative Names + AI
Include variations and alternative names:
- {{alias}} ai
- {{nickname}} ai

**Example for Superman:**
- "clark kent ai"
- "kal-el ai"
- "man of steel ai"

## COMPREHENSIVE KEYWORD GENERATION INSTRUCTIONS

1. **Be EXHAUSTIVE**: Generate keywords for EVERY character + EVERY AI tool combination
2. **Include ALL major AI tools**: sora, runway, kling, pika, luma, veo, veo3, minimax, gen-2, gen-3, midjourney
3. **Add franchise-level keywords**: Not just characters, but the franchise name itself + AI tools
4. **Include variations**: Alternate names, nicknames, locations, objects
5. **Keep it simple**: Format is always "{{name}} {{tool}}" - two words, lowercase
6. **Aim for 50-200 keywords** per IP depending on the number of characters

## Example for Complete IP Configuration

For "DC Universe" with characters [Superman, Batman, Wonder Woman]:

search_keywords: [
  // Superman combinations (13 keywords)
  "superman ai", "superman sora", "superman runway", "superman kling",
  "superman pika", "superman luma", "superman veo", "superman veo3",
  "superman minimax", "superman ai generated", "superman ai movie",
  "clark kent ai", "kal-el ai",

  // Batman combinations (13 keywords)
  "batman ai", "batman sora", "batman runway", "batman kling",
  "batman pika", "batman luma", "batman veo", "batman veo3",
  "batman minimax", "batman ai generated", "batman ai movie",
  "bruce wayne ai", "dark knight ai",

  // Wonder Woman combinations (11 keywords)
  "wonder woman ai", "wonder woman sora", "wonder woman runway",
  "wonder woman kling", "wonder woman pika", "wonder woman luma",
  "wonder woman veo", "wonder woman veo3", "wonder woman ai movie",
  "diana prince ai", "diana ai",

  // Franchise-level keywords (10 keywords)
  "justice league ai", "justice league sora", "justice league runway",
  "justice league veo3", "dc universe ai", "dc comics ai",
  "gotham city ai", "metropolis ai", "batmobile ai", "krypton ai"
]

Total: 47 keywords for 3 characters (comprehensive coverage)

## Other Rules:
- Keep all existing data unless explicitly asked to change it
- Validate that IP IDs use lowercase with underscores (e.g., "mickey_mouse" not "Mickey Mouse")
- Ensure all required fields are present
- Priority weights must be between 0.0 and 2.0
- Be helpful and suggest improvements if the request is unclear
"""

        # Call Gemini
        client = get_gemini_client()
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=genai.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )

        # Parse Gemini response
        gemini_output = json.loads(response.text)
        changes_summary = gemini_output.get("changes_summary", "Changes applied")
        new_config_data = gemini_output.get("new_config")
        warnings = gemini_output.get("warnings", [])

        # Validate new config
        new_config = SystemConfig(**new_config_data)

        # Apply or just propose?
        if request.apply_immediately:
            success = save_system_config(new_config)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to save configuration")

            message = f"✅ Configuration updated: {changes_summary}"
            if warnings:
                message += "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings)

            return ConfigUpdateResponse(
                success=True,
                message=message,
                proposed_changes=gemini_output,
                current_config=current_config,
                new_config=new_config,
                applied=True
            )
        else:
            # Just return for review
            return ConfigUpdateResponse(
                success=True,
                message=f"📝 Proposed changes: {changes_summary}\n\nReview the changes below. Set apply_immediately=true to apply.",
                proposed_changes=gemini_output,
                current_config=current_config,
                new_config=new_config,
                applied=False
            )

    except Exception as e:
        log_exception_json(logger, "Failed to process config update", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {e!s}")


@router.put("", response_model=SystemConfig)
async def update_config_directly(config: SystemConfig):
    """
    Directly update the entire configuration.

    Use this for programmatic updates or when you have the full config ready.
    For natural language updates, use POST /config/update instead.
    """
    try:
        success = save_system_config(config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save configuration")

        return config

    except Exception as e:
        log_exception_json(logger, "Failed to update config", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=str(e))
