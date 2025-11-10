"""Configuration endpoint for frontend.

Configuration is stored in Firestore and loaded dynamically.
"""

import logging
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from google.cloud import firestore
from pydantic import BaseModel

from app.utils.logging_utils import log_exception_json

router = APIRouter(prefix="/config", tags=["configuration"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_configuration() -> dict[str, Any]:
    """
    Get shared configuration for frontend.

    Configuration is loaded from Firestore IP configs.
    """
    # Return empty config - frontend uses API endpoints for data
    return {"status": "Configuration loaded from Firestore", "version": "2.0"}


@router.get("/characters")
async def get_all_characters(priority: str | None = None) -> dict[str, Any]:
    """
    Get all monitored characters.

    Args:
        priority: Optional filter by monitoring priority (high, medium, low)

    Returns:
        {
            "characters": ["Superman", "Batman", ...],
            "total": 44,
            "priority": "high" or null
        }
    """
    if _config is None:
        raise HTTPException(
            status_code=500,
            detail="Configuration not available"
        )

    characters = _config.get_all_characters(priority=priority)

    return {
        "characters": characters,
        "total": len(characters),
        "priority": priority
    }


@router.get("/ips")
async def get_intellectual_properties() -> dict[str, Any]:
    """
    Get all intellectual property definitions.

    Returns:
        {
            "ips": [...],
            "total": 6,
            "client": "Warner Bros. Entertainment"
        }
    """
    if _config is None:
        raise HTTPException(
            status_code=500,
            detail="Configuration not available"
        )

    return {
        "ips": _config.intellectual_properties,
        "total": len(_config.intellectual_properties),
        "client": _config.client_name
    }


@router.get("/client")
async def get_client_info() -> dict[str, Any]:
    """
    Get client information.

    Returns:
        {
            "name": "Warner Bros. Entertainment",
            "abbreviation": "WB",
            "industry": "Entertainment & Media",
            "description": "..."
        }
    """
    if _config is None:
        raise HTTPException(
            status_code=500,
            detail="Configuration not available"
        )

    return _config.to_dict().get("client", {})


@router.get("/list")
async def list_ip_configs() -> dict[str, Any]:
    """
    List all IP target configurations from Firestore.

    Returns all fields including characters, keywords, patterns, etc.
    for all IP configurations created via the Configuration Manager.

    Returns:
        {
            "configs": [
                {
                    "id": "doc_id",
                    "name": "Justice League",
                    "characters": ["Superman", "Batman", ...],
                    "search_keywords": ["justice league", ...],
                    "ai_tool_patterns": ["sora", ...],
                    "visual_keywords": ["cape", "logo", ...],
                    "common_video_titles": ["AI Superman", ...],
                    "false_positive_filters": ["toy", "game", ...],
                    "priority": "high",
                    "tier": "platinum",
                    ...
                }
            ],
            "total": 3
        }
    """
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        docs = db.collection("ip_configs").stream()

        configs = []
        for doc in docs:
            data = doc.to_dict()

            # Skip deleted configs
            if data.get("deleted", False):
                continue

            # Load priority brackets from Firestore
            high_priority = data.get("high_priority_keywords", [])
            medium_priority = data.get("medium_priority_keywords", [])
            low_priority = data.get("low_priority_keywords", [])

            # Combine into search_keywords for discovery service
            all_keywords = high_priority + medium_priority + low_priority
            search_keywords = all_keywords if all_keywords else data.get("search_keywords", [])

            # Also save back to Firestore if we combined them
            if all_keywords and not data.get("search_keywords"):
                doc.reference.update({"search_keywords": search_keywords})

            configs.append({
                "id": doc.id,
                "name": data.get("name", "Unnamed IP"),
                "characters": data.get("characters", []),
                "search_keywords": search_keywords,  # Combined for discovery service
                "high_priority_keywords": high_priority,  # For frontend editing
                "medium_priority_keywords": medium_priority,  # For frontend editing
                "low_priority_keywords": low_priority,  # For frontend editing
                "ai_tool_patterns": data.get("ai_tool_patterns", []),
                "visual_keywords": data.get("visual_keywords", []),
                "common_video_titles": data.get("common_video_titles", []),
                "false_positive_filters": data.get("false_positive_filters", []),
                "priority": data.get("priority", "medium"),
                "priority_weight": data.get("priority_weight", 1.0),
                "tier": data.get("tier", "bronze"),
                "monitoring_strategy": data.get("monitoring_strategy", "balanced"),
                "reasoning": data.get("reasoning", ""),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            })

        logger.info(f"Listed {len(configs)} IP configurations")

        return {
            "configs": configs,
            "total": len(configs)
        }

    except Exception as e:
        log_exception_json(logger, "Failed to list IP configs", e, severity="ERROR")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list IP configurations: {e!s}"
        )


# Pydantic models for update requests
class UpdateFieldRequest(BaseModel):
    """Generic request model for updating array fields."""
    values: list[str]


@router.patch("/{config_id}/characters")
async def update_characters(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update characters list for a config."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        db.collection("ip_configs").document(config_id).update({
            "characters": request.values,
            "updated_at": datetime.utcnow().isoformat()
        })
        logger.info(f"Updated characters for {config_id}: {len(request.values)} items")
        return {"success": True, "count": len(request.values)}
    except Exception as e:
        log_exception_json(logger, "Failed to update characters", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/keywords")
async def update_keywords(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update search keywords list for a config."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        db.collection("ip_configs").document(config_id).update({
            "search_keywords": request.values,
            "updated_at": datetime.utcnow().isoformat()
        })
        logger.info(f"Updated keywords for {config_id}: {len(request.values)} items")
        return {"success": True, "count": len(request.values)}
    except Exception as e:
        log_exception_json(logger, "Failed to update keywords", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/high-priority-keywords")
async def update_high_priority_keywords(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update high priority keywords and recombine into search_keywords."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        doc_ref = db.collection("ip_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Config not found")

        data = doc.to_dict()

        # Update high priority
        high_priority = request.values
        medium_priority = data.get("medium_priority_keywords", [])
        low_priority = data.get("low_priority_keywords", [])

        # Combine all into search_keywords
        search_keywords = high_priority + medium_priority + low_priority

        doc_ref.update({
            "high_priority_keywords": high_priority,
            "search_keywords": search_keywords,  # Combined for discovery!
            "updated_at": datetime.utcnow().isoformat()
        })

        logger.info(f"Updated high priority keywords for {config_id}: {len(high_priority)} items, total search_keywords: {len(search_keywords)}")
        return {"success": True, "count": len(high_priority), "total_keywords": len(search_keywords)}
    except Exception as e:
        log_exception_json(logger, "Failed to update high priority keywords", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/medium-priority-keywords")
async def update_medium_priority_keywords(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update medium priority keywords and recombine into search_keywords."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        doc_ref = db.collection("ip_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Config not found")

        data = doc.to_dict()

        # Update medium priority
        high_priority = data.get("high_priority_keywords", [])
        medium_priority = request.values
        low_priority = data.get("low_priority_keywords", [])

        # Combine all into search_keywords
        search_keywords = high_priority + medium_priority + low_priority

        doc_ref.update({
            "medium_priority_keywords": medium_priority,
            "search_keywords": search_keywords,  # Combined for discovery!
            "updated_at": datetime.utcnow().isoformat()
        })

        logger.info(f"Updated medium priority keywords for {config_id}: {len(medium_priority)} items, total search_keywords: {len(search_keywords)}")
        return {"success": True, "count": len(medium_priority), "total_keywords": len(search_keywords)}
    except Exception as e:
        log_exception_json(logger, "Failed to update medium priority keywords", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/low-priority-keywords")
async def update_low_priority_keywords(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update low priority keywords and recombine into search_keywords."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        doc_ref = db.collection("ip_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Config not found")

        data = doc.to_dict()

        # Update low priority
        high_priority = data.get("high_priority_keywords", [])
        medium_priority = data.get("medium_priority_keywords", [])
        low_priority = request.values

        # Combine all into search_keywords
        search_keywords = high_priority + medium_priority + low_priority

        doc_ref.update({
            "low_priority_keywords": low_priority,
            "search_keywords": search_keywords,  # Combined for discovery!
            "updated_at": datetime.utcnow().isoformat()
        })

        logger.info(f"Updated low priority keywords for {config_id}: {len(low_priority)} items, total search_keywords: {len(search_keywords)}")
        return {"success": True, "count": len(low_priority), "total_keywords": len(search_keywords)}
    except Exception as e:
        log_exception_json(logger, "Failed to update low priority keywords", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/ai-patterns")
async def update_ai_patterns(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update AI tool patterns list for a config."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        db.collection("ip_configs").document(config_id).update({
            "ai_tool_patterns": request.values,
            "updated_at": datetime.utcnow().isoformat()
        })
        logger.info(f"Updated AI patterns for {config_id}: {len(request.values)} items")
        return {"success": True, "count": len(request.values)}
    except Exception as e:
        log_exception_json(logger, "Failed to update AI patterns", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/visual-keywords")
async def update_visual_keywords(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update visual keywords list for a config."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        db.collection("ip_configs").document(config_id).update({
            "visual_keywords": request.values,
            "updated_at": datetime.utcnow().isoformat()
        })
        logger.info(f"Updated visual keywords for {config_id}: {len(request.values)} items")
        return {"success": True, "count": len(request.values)}
    except Exception as e:
        log_exception_json(logger, "Failed to update visual keywords", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/video-titles")
async def update_video_titles(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update common video titles list for a config."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        db.collection("ip_configs").document(config_id).update({
            "common_video_titles": request.values,
            "updated_at": datetime.utcnow().isoformat()
        })
        logger.info(f"Updated video titles for {config_id}: {len(request.values)} items")
        return {"success": True, "count": len(request.values)}
    except Exception as e:
        log_exception_json(logger, "Failed to update video titles", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{config_id}/false-positive-filters")
async def update_false_positive_filters(config_id: str, request: UpdateFieldRequest) -> dict[str, Any]:
    """Update false positive filters list for a config."""
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        db.collection("ip_configs").document(config_id).update({
            "false_positive_filters": request.values,
            "updated_at": datetime.utcnow().isoformat()
        })
        logger.info(f"Updated false positive filters for {config_id}: {len(request.values)} items")
        return {"success": True, "count": len(request.values)}
    except Exception as e:
        log_exception_json(logger, "Failed to update false positive filters", e, severity="ERROR", config_id=config_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}")
async def delete_config(config_id: str) -> dict[str, Any]:
    """
    Soft-delete an IP configuration (marks as deleted, can be restored).

    Args:
        config_id: The ID of the IP config to delete (e.g., "dc-universe")

    Returns:
        Success confirmation with deleted config details
    """
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        doc_ref = db.collection("ip_configs").document(config_id)

        # Get the document first to check if exists
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(
                status_code=404,
                detail=f"IP config '{config_id}' not found"
            )

        config_data = doc.to_dict()
        config_name = config_data.get("name", config_id)

        # Soft delete: mark as deleted instead of removing
        doc_ref.update({
            "deleted": True,
            "deleted_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })

        # Also mark all related videos as deleted
        # Note: videos have matched_ips array, need to check if config_id is in array
        videos_ref = db.collection("videos").where("matched_ips", "array_contains", config_id)
        video_count = 0
        for video_doc in videos_ref.stream():
            video_doc.reference.update({
                "deleted": True,
                "deleted_at": datetime.utcnow().isoformat()
            })
            video_count += 1

        logger.info(f"Soft-deleted IP config: {config_id} ({config_name}) and {video_count} related videos")

        return {
            "success": True,
            "deleted_id": config_id,
            "deleted_name": config_name,
            "deleted_video_count": video_count,
            "message": f"Successfully deleted IP configuration '{config_name}' and {video_count} related videos. You can restore it from the Deleted Configs view."
        }

    except HTTPException:
        raise
    except Exception as e:
        log_exception_json(logger, "Failed to delete config", e, severity="ERROR", config_id=config_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete IP configuration: {e!s}"
        )


@router.get("/list-deleted")
async def list_deleted_configs() -> dict[str, Any]:
    """
    List all deleted IP configurations.

    Returns:
        {
            "configs": [
                {
                    "id": "dc-universe",
                    "name": "DC Universe",
                    "deleted_at": "2025-01-04T10:30:00Z",
                    "deleted_video_count": 150,
                    ...
                }
            ],
            "total": 1
        }
    """
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        docs = db.collection("ip_configs").stream()

        configs = []
        for doc in docs:
            data = doc.to_dict()

            # Only include deleted configs
            if not data.get("deleted", False):
                continue

            # Count related deleted videos
            video_count = 0
            try:
                videos_ref = db.collection("videos").where("matched_ips", "array_contains", doc.id).where("deleted", "==", True)
                video_count = len(list(videos_ref.stream()))
            except Exception as e:
                log_exception_json(logger, "Failed to count deleted videos for config", e, severity="WARNING", config_id=doc.id)

            configs.append({
                "id": doc.id,
                "name": data.get("name", "Unnamed IP"),
                "characters": data.get("characters", []),
                "priority": data.get("priority", "medium"),
                "deleted_at": data.get("deleted_at"),
                "deleted_video_count": video_count,
            })

        logger.info(f"Listed {len(configs)} deleted IP configurations")

        return {
            "configs": configs,
            "total": len(configs)
        }

    except Exception as e:
        log_exception_json(logger, "Failed to list deleted IP configs", e, severity="ERROR")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list deleted IP configurations: {e!s}"
        )


@router.post("/{config_id}/restore")
async def restore_config(config_id: str) -> dict[str, Any]:
    """
    Restore a soft-deleted IP configuration.

    Args:
        config_id: The ID of the IP config to restore (e.g., "dc-universe")

    Returns:
        Success confirmation with restored config details
    """
    try:
        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID", "copycat-local"), database="copycat")
        doc_ref = db.collection("ip_configs").document(config_id)

        # Get the document first to check if exists
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(
                status_code=404,
                detail=f"IP config '{config_id}' not found"
            )

        config_data = doc.to_dict()

        # Check if it's actually deleted
        if not config_data.get("deleted", False):
            raise HTTPException(
                status_code=400,
                detail=f"IP config '{config_id}' is not deleted"
            )

        config_name = config_data.get("name", config_id)

        # Restore: remove deleted flag
        doc_ref.update({
            "deleted": False,
            "deleted_at": None,
            "restored_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })

        # Also restore all related videos
        videos_ref = db.collection("videos").where("matched_ips", "array_contains", config_id).where("deleted", "==", True)
        video_count = 0
        for video_doc in videos_ref.stream():
            video_doc.reference.update({
                "deleted": False,
                "deleted_at": None,
                "restored_at": datetime.utcnow().isoformat()
            })
            video_count += 1

        logger.info(f"Restored IP config: {config_id} ({config_name}) and {video_count} related videos")

        return {
            "success": True,
            "restored_id": config_id,
            "restored_name": config_name,
            "restored_video_count": video_count,
            "message": f"Successfully restored IP configuration '{config_name}' and {video_count} related videos."
        }

    except HTTPException:
        raise
    except Exception as e:
        log_exception_json(logger, "Failed to restore config", e, severity="ERROR", config_id=config_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore IP configuration: {e!s}"
        )
