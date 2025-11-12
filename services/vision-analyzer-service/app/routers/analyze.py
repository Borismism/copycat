"""PubSub push endpoint for video analysis."""

import asyncio
import base64
import json
import logging
import uuid

from fastapi import APIRouter, Request, Response
from google.cloud import firestore
from pydantic import BaseModel

from ..config import settings
from ..models import ScanReadyMessage
from app.utils.logging_utils import log_exception_json

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
firestore_client = None


@router.post("/analyze")
async def analyze_video(request: Request):
    """
    Receive PubSub push messages for video analysis.

    This endpoint is called by PubSub when a scan-ready message is published.

    **CRITICAL BEHAVIOR:**
    - Returns 503 if >490 active requests (PubSub retries on another instance)
    - Returns 200 OK once accepted (even if processing fails)
    - Processes video synchronously in the request (keeps connection alive)
    - Logs all errors properly to Cloud Logging
    - Never retries - marks videos as failed for unsolvable problems

    Returns:
        503: Too many concurrent requests (PubSub will retry)
        200 OK: Message accepted and processed (success or logged failure)
    """
    import app.main as main_module
    global video_analyzer, budget_manager, config_loader, firestore_client

    # Check if we're at capacity (reserve 10 slots for health checks)
    if main_module.active_request_count >= main_module.MAX_CONCURRENT_REQUESTS:
        logger.warning(
            f"⚠️  Rejecting request - at capacity ({main_module.active_request_count}/490 active)"
        )
        return Response(
            content=json.dumps({
                "status": "capacity_exceeded",
                "active_requests": main_module.active_request_count,
                "message": "Service at capacity - PubSub will retry on another instance"
            }),
            status_code=503,
            media_type="application/json"
        )

    # Increment active request counter
    main_module.active_request_count += 1
    start_active_count = main_module.active_request_count

    logger.info(f"📥 Request accepted (active: {start_active_count}/490)")

    if not video_analyzer or not budget_manager or not config_loader or not firestore_client:
        main_module.active_request_count -= 1
        logger.error("Service components not initialized")
        return Response(
            content=json.dumps({
                "status": "error",
                "message": "Service not ready - components not initialized"
            }),
            status_code=200,  # Return 200 to prevent PubSub retry
            media_type="application/json"
        )

    scan_id = None
    video_id = None

    try:
        # Parse PubSub push message
        body = await request.json()

        if "message" not in body:
            logger.error(f"Invalid PubSub message format: {body}")
            return Response(
                content=json.dumps({"status": "error", "message": "Invalid message format"}),
                status_code=200,  # Don't retry invalid messages
                media_type="application/json"
            )

        # Decode base64 message data
        message_data = base64.b64decode(body["message"]["data"]).decode("utf-8")
        data = json.loads(message_data)

        # Parse scan-ready message
        scan_message = ScanReadyMessage(**data)
        video_id = scan_message.video_id
        scan_priority = getattr(scan_message.metadata, 'scan_priority', None)

        logger.info(
            f"🎬 Processing video {video_id}: priority={scan_message.priority}, "
            f"scan_priority={scan_priority}"
        )

        # Check scan priority threshold
        if scan_priority is not None and scan_priority < MINIMUM_SCAN_PRIORITY:
            logger.info(
                f"Skipping video {video_id}: scan_priority {scan_priority} < "
                f"minimum {MINIMUM_SCAN_PRIORITY}"
            )

            # Update video status to skipped
            try:
                doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(video_id)
                doc_ref.update({
                    "status": "skipped_low_priority",
                    "skip_reason": f"scan_priority {scan_priority} < minimum {MINIMUM_SCAN_PRIORITY}",
                    "skipped_at": firestore.SERVER_TIMESTAMP
                })
            except Exception as e:
                logger.warning(f"Failed to update skipped video status: {e}")

            return Response(
                content=json.dumps({"status": "skipped", "video_id": video_id}),
                status_code=200,
                media_type="application/json"
            )

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
            logger.info(f"Created scan history: {scan_id}")
        except Exception as e:
            logger.warning(f"Failed to create scan history: {e}")
            # Continue anyway - not critical

        # Update video status to "processing"
        try:
            doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(video_id)
            doc_ref.update({
                "status": "processing",
                "processing_started_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Updated video {video_id} status to 'processing'")
        except Exception as e:
            logger.warning(f"Failed to update video status to processing: {e}")
            # Continue anyway - not critical

        # Load IP configs for this video
        matched_ips = scan_message.metadata.matched_ips

        # If no IPs matched, scan against ALL IPs
        if not matched_ips:
            logger.info(f"⚠️  No matched_ips for video {video_id}. Loading ALL IP configs.")
            configs = config_loader.get_all_configs()
            if not configs:
                logger.error("❌ No IP configs available in system!")

                # Update scan history
                try:
                    firestore_client.collection("scan_history").document(scan_id).update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": "No IP configs available in system",
                    })
                except Exception as e:
                    logger.error(f"Failed to update scan history: {e}")

                # Update video status
                try:
                    doc_ref.update({
                        "status": "failed",
                        "error_message": "No IP configs available in system",
                        "error_type": "ConfigurationError",
                        "failed_at": firestore.SERVER_TIMESTAMP,
                    })
                except Exception as e:
                    logger.error(f"Failed to update video status: {e}")

                return Response(
                    content=json.dumps({"status": "error", "video_id": video_id, "message": "No IP configs"}),
                    status_code=200,  # Don't retry - system config problem
                    media_type="application/json"
                )
            logger.info(f"✅ Loaded {len(configs)} IP configs for comprehensive scan")
        else:
            # Load specific IP configs
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
                logger.error(f"❌ No valid configs for video {video_id}. matched_ips={matched_ips}.")

                # Update scan history
                try:
                    firestore_client.collection("scan_history").document(scan_id).update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": f"No IP configs found for matched_ips={matched_ips}",
                    })
                except Exception as e:
                    logger.error(f"Failed to update scan history: {e}")

                # Update video status
                try:
                    doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(video_id)
                    doc_ref.update({
                        "status": "failed",
                        "error_message": f"No IP configs found for matched_ips={matched_ips}",
                        "error_type": "ConfigurationError",
                        "failed_at": firestore.SERVER_TIMESTAMP,
                    })
                except Exception as e:
                    logger.error(f"Failed to update video status: {e}")

                return Response(
                    content=json.dumps({"status": "error", "video_id": video_id, "message": f"No configs for {matched_ips}"}),
                    status_code=200,  # Don't retry - data problem
                    media_type="application/json"
                )

        # Process video analysis synchronously (keeps connection alive)
        logger.info(f"🚀 Starting video analysis for {video_id}")

        try:
            result = await video_analyzer.analyze_video(
                video_metadata=scan_message.metadata,
                configs=configs,
                queue_size=1
            )

            has_infringement = any(ip.contains_infringement for ip in result.analysis.ip_results)
            logger.info(
                f"✅ Successfully processed video {video_id}: "
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
                log_exception_json(logger, "Failed to update scan history", e, severity="WARNING")

            return Response(
                content=json.dumps({
                    "status": "success",
                    "video_id": video_id,
                    "scan_id": scan_id,
                    "has_infringement": has_infringement,
                    "recommendation": result.analysis.overall_recommendation
                }),
                status_code=200,
                media_type="application/json"
            )

        except Exception as e:
            log_exception_json(logger, f"Video analysis failed for {video_id}", e, severity="ERROR")

            # Categorize failure type and determine response code
            error_str = str(e)
            error_type = type(e).__name__

            # Check for different error types and return appropriate HTTP codes
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                # Rate limit - return 429 for PubSub retry
                logger.warning(f"Rate limited for video {video_id}, returning 429 for retry")
                # Don't update status - stay "processing" during retries
                return Response(
                    content=json.dumps({
                        "status": "rate_limited",
                        "video_id": video_id,
                        "message": "Rate limited - will retry"
                    }),
                    status_code=429,  # PubSub will retry with backoff
                    media_type="application/json"
                )

            elif "PERMISSION_DENIED" in error_str or "not accessible" in error_str:
                # Permanent failure - return 200 (don't retry)
                video_status = "inaccessible"
                scan_status = "failed"
                error_message = f"Video not accessible: {error_str[:200]}"
                logger.warning(f"Video {video_id} is inaccessible")
                response_code = 200  # Don't retry

            elif error_type == "TimeoutError" or "timed out" in error_str.lower():
                # Timeout - return 504 for retry
                logger.warning(f"Video {video_id} analysis timed out, returning 504 for retry")
                # Don't update status - stay "processing" during retries
                return Response(
                    content=json.dumps({
                        "status": "timeout",
                        "video_id": video_id,
                        "message": "Request timed out - will retry"
                    }),
                    status_code=504,  # PubSub will retry
                    media_type="application/json"
                )

            elif "ConnectionError" in error_str or "NetworkError" in error_str or "ssl.SSLError" in error_str:
                # Network error - return 503 for retry
                logger.warning(f"Network error for video {video_id}, returning 503 for retry")
                # Don't update status - stay "processing" during retries
                return Response(
                    content=json.dumps({
                        "status": "network_error",
                        "video_id": video_id,
                        "message": "Network error - will retry"
                    }),
                    status_code=503,  # PubSub will retry
                    media_type="application/json"
                )

            elif error_type == "ValueError" and "Invalid JSON" in error_str:
                # Gemini returned malformed JSON - permanent failure (won't fix itself on retry)
                video_status = "failed"
                scan_status = "failed"
                error_message = f"Gemini API returned invalid JSON: {error_str[:200]}"
                logger.error(f"Video {video_id} failed due to Gemini JSON parse error")
                response_code = 200  # Don't retry - Gemini bug won't fix itself

            else:
                # Unknown error - return 500 for limited retry
                logger.error(f"Unknown error for video {video_id}: {error_str[:200]}")
                # Don't update status - let PubSub retry a few times
                return Response(
                    content=json.dumps({
                        "status": "error",
                        "video_id": video_id,
                        "error_type": error_type,
                        "message": error_str[:200]
                    }),
                    status_code=500,  # PubSub will retry (limited)
                    media_type="application/json"
                )

            # Only reach here for permanent failures (PERMISSION_DENIED)
            # Update scan history
            try:
                firestore_client.collection("scan_history").document(scan_id).update({
                    "status": scan_status,
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "error_message": error_message,
                    "error_type": error_type,
                })
            except Exception as update_error:
                log_exception_json(logger, "Failed to update scan history", update_error, severity="WARNING")

            # Update video status
            try:
                doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(video_id)
                doc_ref.update({
                    "status": video_status,
                    "error_message": error_message,
                    "error_type": error_type,
                    "failed_at": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"Updated video {video_id} status to '{video_status}'")
            except Exception as update_error:
                log_exception_json(logger, "Failed to update video status", update_error, severity="WARNING")

            return Response(
                content=json.dumps({
                    "status": "failed",
                    "video_id": video_id,
                    "scan_id": scan_id,
                    "error_type": error_type,
                    "error_message": error_message[:200]
                }),
                status_code=response_code,
                media_type="application/json"
            )

    except Exception as e:
        log_exception_json(logger, "Failed to process PubSub message", e, severity="ERROR")

        # Don't update any status - let PubSub retry
        # Return 500 for unknown/unexpected errors
        return Response(
            content=json.dumps({
                "status": "error",
                "video_id": video_id,
                "message": str(e)[:200]
            }),
            status_code=500,  # PubSub will retry (limited)
            media_type="application/json"
        )

    finally:
        # Decrement active request counter
        main_module.active_request_count -= 1
        end_active_count = main_module.active_request_count
        logger.info(f"✅ Request completed (active: {end_active_count}/490)")
