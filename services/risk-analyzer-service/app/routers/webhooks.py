"""PubSub webhook endpoints for PUSH subscriptions."""

import base64
import json
import logging
from fastapi import APIRouter, Request

from google.cloud import firestore
from ..core.risk_analyzer import RiskAnalyzer
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/process/video-discovered")
async def process_video_discovered(request: Request):
    """Handle PubSub push for video-discovered topic."""
    try:
        envelope = await request.json()

        # Decode PubSub message
        if "message" not in envelope:
            logger.error("Invalid PubSub message format")
            return {"status": "error", "message": "Invalid format"}

        message = envelope["message"]
        data = base64.b64decode(message["data"]).decode("utf-8")
        video_data = json.loads(data)

        logger.info(f"Received video-discovered: {video_data.get('video_id')}")

        # Process with risk analyzer
        from ..config import settings
        firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id
        )
        analyzer = RiskAnalyzer(
            firestore_client=firestore_client,
            pubsub_subscriber=None,  # Not needed for processing
        )

        await analyzer.process_video_discovered(video_data)

        return {"status": "ok"}

    except Exception as e:
        log_exception_json(logger, "Error processing video-discovered", e, severity="ERROR")
        # Return 200 anyway to avoid retries for unrecoverable errors
        return {"status": "error", "message": str(e)}


@router.post("/process/vision-feedback")
async def process_vision_feedback(request: Request):
    """Handle PubSub push for vision-feedback topic."""
    try:
        envelope = await request.json()

        # Decode PubSub message
        if "message" not in envelope:
            logger.error("Invalid PubSub message format")
            return {"status": "error", "message": "Invalid format"}

        message = envelope["message"]
        data = base64.b64decode(message["data"]).decode("utf-8")
        feedback_data = json.loads(data)

        logger.info(f"Received vision-feedback: {feedback_data.get('video_id')}")

        # Process with risk analyzer
        from ..config import settings
        firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id
        )
        analyzer = RiskAnalyzer(
            firestore_client=firestore_client,
            pubsub_subscriber=None,
        )

        await analyzer.process_vision_feedback(feedback_data)

        return {"status": "ok"}

    except Exception as e:
        log_exception_json(logger, "Error processing vision-feedback", e, severity="ERROR")
        return {"status": "error", "message": str(e)}
