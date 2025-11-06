"""PubSub push endpoint for video analysis."""

import base64
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from google.cloud import firestore
from pydantic import BaseModel

from ..config import settings
from ..models import ScanReadyMessage

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration constants
MINIMUM_SCAN_PRIORITY = 0  # Scan everything from top to bottom until budget depleted


class PubSubMessage(BaseModel):
    """PubSub push message format."""

    message: dict
    subscription: str


# Global components (initialized in main.py startup)
video_analyzer = None
budget_manager = None
config_loader = None


@router.post("/analyze")
async def analyze_video(request: Request):
    """
    Receive PubSub push messages for video analysis.

    This endpoint is called by PubSub when a scan-ready message is published.

    Returns:
        200 OK: Message processed successfully (or failed gracefully)
        500 Error: Message should be retried
    """
    global video_analyzer, budget_manager, config_loader

    if not video_analyzer or not budget_manager or not config_loader:
        logger.error("Service components not initialized")
        raise HTTPException(status_code=503, detail="Service not ready")

    scan_id = None  # Initialize scan_id for error handling
    firestore_client = None
    video_id = None

    try:
        # Parse PubSub push message
        body = await request.json()

        if "message" not in body:
            logger.error(f"Invalid PubSub message format: {body}")
            return {"status": "error", "message": "Invalid message format"}

        # Decode base64 message data
        message_data = base64.b64decode(body["message"]["data"]).decode("utf-8")
        data = json.loads(message_data)

        # Parse scan-ready message
        scan_message = ScanReadyMessage(**data)
        video_id = scan_message.video_id
        scan_priority = getattr(scan_message.metadata, 'scan_priority', None)

        logger.info(
            f"Received scan-ready message: video={video_id}, "
            f"priority={scan_message.priority}, scan_priority={scan_priority}"
        )

        firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id,
        )

        # Check scan priority threshold
        if scan_priority is not None and scan_priority < MINIMUM_SCAN_PRIORITY:
            logger.info(
                f"Skipping video {video_id}: scan_priority {scan_priority} < "
                f"minimum {MINIMUM_SCAN_PRIORITY} (tier: {scan_message.priority})"
            )

            # Update video status to skipped
            try:
                doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(
                    video_id
                )
                doc_ref.update({
                    "status": "skipped_low_priority",
                    "skip_reason": f"scan_priority {scan_priority} < minimum {MINIMUM_SCAN_PRIORITY}",
                    "skipped_at": firestore.SERVER_TIMESTAMP
                })
            except Exception as e:
                logger.warning(f"Failed to update skipped video status: {e}")

            # Return 200 OK (message processed, don't retry)
            return {"status": "skipped", "video_id": video_id}

        # Create scan history entry
        scan_id = str(uuid.uuid4())

        scan_history = {
            "scan_id": scan_id,
            "scan_type": "video_single",
            "video_id": scan_message.video_id,
            "video_title": scan_message.metadata.title,
            "channel_id": scan_message.metadata.channel_id,
            "channel_title": scan_message.metadata.channel_title,
            "status": "running",
            "started_at": firestore.SERVER_TIMESTAMP,
            "matched_ips": scan_message.metadata.matched_ips,
        }

        try:
            firestore_client.collection("scan_history").document(scan_id).set(scan_history)
            logger.info(f"Created scan history: {scan_id} for video {scan_message.video_id}")
        except Exception as e:
            logger.warning(f"Failed to create scan history: {e}")
            # Continue anyway - not critical

        # Update video status to "processing"
        try:
            doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(
                scan_message.video_id
            )
            doc_ref.update({
                "status": "processing",
                "processing_started_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Updated video {scan_message.video_id} status to 'processing'")
        except Exception as e:
            logger.warning(f"Failed to update video status to processing: {e}")
            # Continue anyway - not critical

        # Load IP configs for this video
        matched_ips = scan_message.metadata.matched_ips

        # If no IPs matched, scan against ALL IPs to catch potential infringements
        if not matched_ips:
            logger.info(
                f"⚠️  No matched_ips for video {scan_message.video_id}. "
                "Loading ALL IP configs for comprehensive scan."
            )
            configs = config_loader.get_all_configs()
            if configs:
                logger.info(f"✅ Loaded {len(configs)} IP configs for comprehensive scan")
            else:
                logger.error("❌ No IP configs available in system!")
                # Update scan history to failed
                try:
                    firestore_client.collection("scan_history").document(scan_id).update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": "No IP configs available in system",
                    })
                except Exception as e:
                    logger.error(f"Failed to update scan history: {e}")

                # Update video status to failed
                try:
                    doc_ref = firestore_client.collection(
                        settings.firestore_videos_collection
                    ).document(scan_message.video_id)
                    doc_ref.update({
                        "status": "failed",
                        "error_message": "No IP configs available in system",
                        "error_type": "ConfigurationError",
                        "failed_at": firestore.SERVER_TIMESTAMP,
                    })
                except Exception as e:
                    logger.error(f"Failed to update video status: {e}")

                # Return 200 OK (don't retry - this is a system configuration problem)
                return {"status": "error", "video_id": video_id, "message": "No IP configs available"}
        else:
            # Load specific IP configs that matched
            logger.info(f"Loading configs for matched IPs: {matched_ips}")
            configs = []
            for ip_id in matched_ips:
                config = config_loader.get_config(ip_id)
                if config:
                    configs.append(config)
                    logger.info(f"✅ Loaded config: {config.name}")
                else:
                    logger.error(f"❌ Config not found for IP: {ip_id}")

            if not configs:
                logger.error(
                    f"❌ No valid configs for video {scan_message.video_id}. "
                    f"matched_ips={matched_ips}."
                )
                # Update scan history to failed
                try:
                    firestore_client.collection("scan_history").document(scan_id).update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": f"No IP configs found for matched_ips={matched_ips}",
                    })
                except Exception as e:
                    logger.error(f"Failed to update scan history: {e}")

                # Update video status to failed
                try:
                    doc_ref = firestore_client.collection(
                        settings.firestore_videos_collection
                    ).document(scan_message.video_id)
                    doc_ref.update({
                        "status": "failed",
                        "error_message": f"No IP configs found for matched_ips={matched_ips}",
                        "error_type": "ConfigurationError",
                        "failed_at": firestore.SERVER_TIMESTAMP,
                    })
                except Exception as e:
                    logger.error(f"Failed to update video status: {e}")

                # Return 200 OK (don't retry - this is a data problem)
                return {"status": "error", "video_id": video_id, "message": f"No configs for {matched_ips}"}

        # Process video analysis with configs
        result = await video_analyzer.analyze_video(
            video_metadata=scan_message.metadata, configs=configs, queue_size=1
        )

        has_infringement = any(ip.contains_infringement for ip in result.analysis.ip_results)
        logger.info(
            f"Successfully processed video {scan_message.video_id}: "
            f"infringement={has_infringement}, "
            f"action={result.analysis.overall_recommendation}"
        )

        # Update scan history to completed
        try:
            firestore_client.collection("scan_history").document(scan_id).update({
                "status": "completed",
                "completed_at": firestore.SERVER_TIMESTAMP,
                "result": {
                    "success": True,
                    "has_infringement": has_infringement,
                    "overall_recommendation": result.analysis.overall_recommendation,
                    "cost_usd": result.metrics.cost_usd,
                    "ip_count": len(result.analysis.ip_results),
                }
            })
            logger.info(f"Updated scan history {scan_id} to completed")
        except Exception as e:
            logger.error(f"Failed to update scan history: {e}", exc_info=True)

        # Return 200 OK (message processed successfully)
        return {
            "status": "success",
            "video_id": video_id,
            "has_infringement": has_infringement,
            "cost_usd": result.metrics.cost_usd
        }

    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)

        # Update scan history to failed (only if scan_id was created)
        if scan_id and firestore_client:
            try:
                firestore_client.collection("scan_history").document(scan_id).update({
                    "status": "failed",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "error_message": str(e),
                })
                logger.info(f"Updated scan history {scan_id} to failed")
            except:
                pass

        # Update video status to failed with error details
        if video_id and firestore_client:
            try:
                doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(
                    video_id
                )
                doc_ref.update({
                    "status": "failed",
                    "error_message": str(e),
                    "error_type": type(e).__name__,
                    "failed_at": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"Updated video {video_id} status to 'failed' with error: {e}")
            except Exception as update_error:
                logger.error(f"Failed to update video status to failed: {update_error}")

        # Return 200 OK (we marked it as failed, don't retry)
        return {"status": "error", "video_id": video_id, "message": str(e)}
