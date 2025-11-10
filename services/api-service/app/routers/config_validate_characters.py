"""
Character validation endpoint using Gemini AI
"""
import logging
import os

from fastapi import APIRouter, HTTPException
from google import genai
from google.auth import default
from google.cloud import firestore
from pydantic import BaseModel

from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)
router = APIRouter()


class ValidateCharactersRequest(BaseModel):
    ip_name: str
    existing_characters: list[str]
    proposed_input: str


class ValidateCharactersResponse(BaseModel):
    valid_characters: list[str]
    reasoning: str


class AddCharactersRequest(BaseModel):
    ip_id: str
    new_characters: list[str]


class AddCharactersResponse(BaseModel):
    success: bool
    updated_characters: list[str]
    message: str


@router.post("/api/config/ai/validate-characters", response_model=ValidateCharactersResponse)
async def validate_characters(request: ValidateCharactersRequest):
    """
    Validate that proposed characters belong to the specified IP using Gemini AI.
    """
    try:
        # Initialize Gemini client
        _credentials, _project = default()
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT", "copycat-429012"),
            location=os.getenv("GEMINI_LOCATION", "europe-west1")
        )

        # Create validation prompt
        prompt = f"""You are validating which characters belong to the "{request.ip_name}" intellectual property.

EXISTING CHARACTERS:
{', '.join(request.existing_characters)}

USER WANTS TO ADD:
{request.proposed_input}

Your task:
1. Parse the user's input and identify individual character names
2. Validate which of these characters actually belong to {request.ip_name}
3. ONLY include characters that are directly part of {request.ip_name} (not spin-offs, not other IPs)
4. Return a JSON object with:
   - valid_characters: array of valid character names (cleaned up, proper capitalization)
   - reasoning: brief explanation of which were valid and which were rejected

IMPORTANT:
- Be strict: only include characters that truly belong to this IP
- Clean up names (e.g., "alfred" → "Alfred Pennyworth")
- Skip duplicates of existing characters
- If a character doesn't belong, explain why in reasoning

Example input: "alfred, spiderman, commissioner gordon"
Example for Batman IP:
{{
  "valid_characters": ["Alfred Pennyworth", "Commissioner Gordon"],
  "reasoning": "Added Alfred Pennyworth and Commissioner Gordon (both Batman characters). Rejected Spider-Man (Marvel character, not DC)."
}}

Respond ONLY with valid JSON, no other text."""

        # Call Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.3,  # Low temp for consistent validation
                "response_mime_type": "application/json"
            }
        )

        # Parse response
        import json
        result = json.loads(response.text)

        return ValidateCharactersResponse(
            valid_characters=result.get("valid_characters", []),
            reasoning=result.get("reasoning", "")
        )

    except Exception as e:
        log_exception_json(logger, "Failed to validate characters", e, severity="ERROR", ip_name=request.ip_name)
        raise HTTPException(
            status_code=500,
            detail=f"Gemini API error: {e!s}"
        )


@router.post("/api/config/ai/add-characters", response_model=AddCharactersResponse)
async def add_characters(request: AddCharactersRequest):
    """
    Add validated characters to an IP configuration in Firestore.
    """
    try:
        # Initialize Firestore
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"))

        # Get the IP config document
        doc_ref = db.collection("ip_targets").document(request.ip_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(
                status_code=404,
                detail=f"IP configuration '{request.ip_id}' not found"
            )

        # Get current characters
        config_data = doc.to_dict()
        current_characters = config_data.get("characters", [])

        # Merge new characters (avoid duplicates)
        updated_characters = list(set(current_characters + request.new_characters))
        updated_characters.sort()  # Keep them alphabetically sorted

        # Update Firestore
        doc_ref.update({
            "characters": updated_characters
        })

        logger.info(f"Added {len(request.new_characters)} characters to {request.ip_id}")

        return AddCharactersResponse(
            success=True,
            updated_characters=updated_characters,
            message=f"Successfully added {len(request.new_characters)} new characters"
        )

    except HTTPException:
        raise
    except Exception as e:
        log_exception_json(logger, "Failed to add characters", e, severity="ERROR", ip_id=request.ip_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {e!s}"
        )


class SaveIPConfigRequest(BaseModel):
    name: str
    owner: str
    description: str
    main_characters: list[str]
    high_priority_keywords: list[str]
    medium_priority_keywords: list[str]
    low_priority_keywords: list[str]
    visual_keywords: list[str]
    character_variations: list[str]
    ai_tool_patterns: list[str]
    common_video_titles: list[str]
    false_positive_filters: list[str]
    priority_weight: float
    monitoring_strategy: str
    reasoning: str


class SaveIPConfigResponse(BaseModel):
    success: bool
    ip_id: str
    message: str


@router.post("/api/config/ai/save", response_model=SaveIPConfigResponse)
async def save_ip_config(request: SaveIPConfigRequest):
    """
    Save a new IP configuration to Firestore.
    """
    try:
        # Initialize Firestore
        db = firestore.Client(
            project=os.getenv("GCP_PROJECT_ID", "copycat-local"),
            database=os.getenv("FIRESTORE_DATABASE", "copycat")
        )

        # Generate IP ID from name (lowercase, hyphenated)
        ip_id = request.name.lower().replace(" ", "-").replace("'", "")

        # Check if already exists
        doc_ref = db.collection("ip_configs").document(ip_id)
        if doc_ref.get().exists:
            raise HTTPException(
                status_code=409,
                detail=f"IP configuration '{request.name}' already exists"
            )

        # Determine priority from monitoring_strategy (more reliable than priority_weight)
        priority = "high"  # Default
        if "aggressive" in request.monitoring_strategy.lower() or request.priority_weight >= 1.5:
            priority = "high"
        elif "balanced" in request.monitoring_strategy.lower() or request.priority_weight >= 1.0:
            priority = "medium"
        elif "selective" in request.monitoring_strategy.lower() or request.priority_weight < 1.0:
            priority = "low"

        # Create config document
        config_data = {
            "name": request.name,
            "owner": request.owner,
            "description": request.description,
            "type": "franchise",  # Default type
            "characters": request.main_characters,
            "high_priority_keywords": request.high_priority_keywords,
            "medium_priority_keywords": request.medium_priority_keywords,
            "low_priority_keywords": request.low_priority_keywords,
            "visual_keywords": request.visual_keywords,
            "character_variations": request.character_variations,
            "ai_tool_patterns": request.ai_tool_patterns,
            "common_video_titles": request.common_video_titles,
            "false_positive_filters": request.false_positive_filters,
            "priority": priority,
            "priority_weight": request.priority_weight,
            "monitoring_strategy": request.monitoring_strategy,
            "reasoning": request.reasoning,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        # Save to Firestore
        doc_ref.set(config_data)

        logger.info(f"Created new IP configuration: {ip_id}")

        return SaveIPConfigResponse(
            success=True,
            ip_id=ip_id,
            message=f"Successfully created IP configuration for '{request.name}'"
        )

    except HTTPException:
        raise
    except Exception as e:
        log_exception_json(logger, "Failed to save IP config", e, severity="ERROR", ip_name=request.name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save configuration: {e!s}"
        )


@router.get("/api/config/list")
async def list_ip_configs():
    """
    List all IP configurations from Firestore.
    """
    try:
        # Initialize Firestore
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"))

        # Get all IP target documents
        docs = db.collection("ip_targets").stream()

        configs = []
        for doc in docs:
            data = doc.to_dict()
            configs.append({
                "id": doc.id,
                "name": data.get("name"),
                "owner": data.get("owner"),
                "type": data.get("type", "franchise"),
                "tier": data.get("tier", "1"),
                "characters": data.get("characters", []),
                "priority": data.get("priority", "medium"),
            })

        return {"configs": configs}

    except Exception as e:
        log_exception_json(logger, "Failed to list IP configs", e, severity="ERROR")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list configurations: {e!s}"
        )
