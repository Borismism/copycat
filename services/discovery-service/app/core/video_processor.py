"""Video processing operations - zero duplication."""

import logging
import re
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore, pubsub_v1

from ..config import settings
from ..models import VideoMetadata, VideoStatus
from .ip_loader import IPTargetManager

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Handles ALL video processing operations.

    Single source of truth for:
    - Metadata extraction from YouTube API
    - Duplicate detection
    - IP matching
    - Firestore persistence
    - PubSub publishing

    Zero duplication across all discovery methods.
    """

    def __init__(
        self,
        firestore_client: firestore.Client,
        pubsub_publisher: pubsub_v1.PublisherClient,
        ip_manager: IPTargetManager,
        topic_path: str,
    ):
        """
        Initialize video processor.

        Args:
            firestore_client: Firestore client for data persistence
            pubsub_publisher: PubSub client for event publishing
            ip_manager: IP target manager for content matching
            topic_path: Full PubSub topic path (projects/X/topics/Y)
        """
        self.firestore = firestore_client
        self.publisher = pubsub_publisher
        self.ip_manager = ip_manager
        self.topic_path = topic_path
        self.videos_collection = "videos"

        logger.info("VideoProcessor initialized")

    def extract_metadata(self, video_data: dict[str, Any]) -> VideoMetadata:
        """
        Extract structured metadata from YouTube API response.

        Handles both search results and video.list responses:
        - search.list: id is {"videoId": "xxx"}
        - videos.list: id is "xxx"

        Args:
            video_data: Raw video data from YouTube API

        Returns:
            Structured video metadata with all fields

        Raises:
            KeyError: If required fields (id, snippet) are missing
            ValueError: If video_id cannot be extracted
        """
        # Extract video ID (handle both search and videos.list formats)
        video_id = video_data.get("id")
        if isinstance(video_id, dict):
            video_id = video_id.get("videoId", "")

        if not video_id:
            raise ValueError("Cannot extract video_id from video_data")

        snippet = video_data.get("snippet", {})
        statistics = video_data.get("statistics", {})
        content_details = video_data.get("contentDetails", {})

        # Parse published date
        published_at_str = snippet.get("publishedAt", "")
        try:
            published_at = datetime.fromisoformat(
                published_at_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            logger.warning(
                f"Invalid publishedAt for video {video_id}: {published_at_str}"
            )
            published_at = datetime.now(timezone.utc)

        # Parse ISO 8601 duration (PT1H2M3S)
        duration_str = content_details.get("duration", "PT0S")
        duration_seconds = self._parse_duration(duration_str)

        # Extract thumbnail (prefer high quality)
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("high", {}).get("url", "")
            or thumbnails.get("medium", {}).get("url", "")
            or thumbnails.get("default", {}).get("url", "")
        )

        return VideoMetadata(
            video_id=video_id,
            title=snippet.get("title", ""),
            channel_id=snippet.get("channelId", ""),
            channel_title=snippet.get("channelTitle", ""),
            published_at=published_at,
            description=snippet.get("description", ""),
            view_count=int(statistics.get("viewCount", 0)),
            like_count=int(statistics.get("likeCount", 0)),
            comment_count=int(statistics.get("commentCount", 0)),
            duration_seconds=duration_seconds,
            tags=snippet.get("tags", []),
            category_id=snippet.get("categoryId", ""),
            thumbnail_url=thumbnail_url,
        )

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse ISO 8601 duration to seconds.

        Format: PT[hours]H[minutes]M[seconds]S
        Examples:
        - PT5M30S = 5 minutes 30 seconds = 330 seconds
        - PT1H15M = 1 hour 15 minutes = 4500 seconds
        - PT45S = 45 seconds

        Args:
            duration_str: ISO 8601 duration string

        Returns:
            Total seconds (0 if parsing fails)
        """
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_str)

        if not match:
            logger.warning(f"Cannot parse duration: {duration_str}")
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

    def is_duplicate(self, video_id: str, max_age_days: int = 7) -> bool:
        """
        Check if video was processed recently.

        A video is considered duplicate if:
        1. It exists in Firestore, AND
        2. It was discovered within last max_age_days

        Rationale: Re-scan old videos to track view growth,
        but avoid scanning same video multiple times per week.

        Args:
            video_id: YouTube video ID
            max_age_days: Consider duplicate if within this many days

        Returns:
            True if duplicate (skip processing), False if new
        """
        doc_ref = self.firestore.collection(self.videos_collection).document(video_id)

        try:
            doc = doc_ref.get()

            if not doc.exists:
                return False

            video_data = doc.to_dict()
            discovered_at = video_data.get("discovered_at")

            if not discovered_at:
                # Old document without timestamp - not a duplicate
                return False

            days_since_scan = (datetime.now(timezone.utc) - discovered_at).days

            is_recent = days_since_scan < max_age_days

            if is_recent:
                logger.debug(
                    f"Video {video_id} is duplicate "
                    f"(scanned {days_since_scan} days ago)"
                )

            return is_recent

        except Exception as e:
            logger.error(f"Error checking duplicate for {video_id}: {e}")
            # On error, assume not duplicate (better to process than skip)
            return False

    def match_ips(self, metadata: VideoMetadata) -> list[str]:
        """
        Match video content against configured IP targets.

        Searches across:
        - Video title
        - Video description
        - Video tags
        - Channel name

        Uses IP target keywords and regex patterns from ip_targets.yaml.

        Args:
            metadata: Video metadata to analyze

        Returns:
            List of matched IP names (empty if no matches)
        """
        # Combine all searchable text
        text_to_check = " ".join(
            [
                metadata.title,
                metadata.description,
                " ".join(metadata.tags),
                metadata.channel_title,
            ]
        )

        # Match against IP targets
        matched_targets = self.ip_manager.match_content(text_to_check)

        if matched_targets:
            ip_names = [ip.name for ip in matched_targets]
            logger.info(f"Video {metadata.video_id} matched IPs: {', '.join(ip_names)}")
            return ip_names

        return []

    def save_and_publish(self, metadata: VideoMetadata) -> bool:
        """
        Atomically save to Firestore and publish to PubSub.

        Operations:
        1. Save video document to Firestore
        2. Publish video message to PubSub

        Both operations must succeed. If either fails, logs error
        but doesn't raise (allows processing to continue).

        Args:
            metadata: Video metadata to persist

        Returns:
            True if both operations succeeded, False otherwise
        """
        try:
            # Save to Firestore
            doc_ref = self.firestore.collection(self.videos_collection).document(
                metadata.video_id
            )

            video_doc = {
                **metadata.model_dump(),
                "status": VideoStatus.DISCOVERED.value,
                "discovered_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            doc_ref.set(video_doc)
            logger.info(f"Saved video {metadata.video_id} to Firestore")

            # Publish to PubSub
            message_data = metadata.model_dump_json().encode("utf-8")
            future = self.publisher.publish(self.topic_path, message_data)
            message_id = future.result(timeout=settings.pubsub_timeout_seconds)

            logger.info(f"Published video {metadata.video_id} to PubSub: {message_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to save/publish video {metadata.video_id}: {e}")
            return False

    def process_batch(
        self,
        video_data_list: list[dict[str, Any]],
        skip_duplicates: bool = True,
        skip_no_ip_match: bool = False,
    ) -> list[VideoMetadata]:
        """
        Process multiple videos efficiently.

        Pipeline:
        1. Extract metadata from all videos
        2. Filter duplicates (optional)
        3. Match IPs
        4. Filter videos with no IP matches (optional)
        5. Save to Firestore + publish to PubSub

        Args:
            video_data_list: Raw video data from YouTube API
            skip_duplicates: Skip videos processed recently
            skip_no_ip_match: Skip videos with no IP matches (default: False - trust YouTube's search)

        Returns:
            Successfully processed videos (with IP matches)
        """
        if not video_data_list:
            return []

        processed = []
        skipped_duplicate = 0
        skipped_no_match = 0
        errors = 0

        logger.info(f"Processing batch of {len(video_data_list)} videos")

        for video_data in video_data_list:
            try:
                # Extract metadata
                metadata = self.extract_metadata(video_data)

                # Check duplicates
                if skip_duplicates and self.is_duplicate(metadata.video_id):
                    skipped_duplicate += 1
                    continue

                # Match IPs
                matched_ips = self.match_ips(metadata)

                if not matched_ips:
                    if skip_no_ip_match:
                        skipped_no_match += 1
                        continue

                metadata.matched_ips = matched_ips

                # Save and publish
                if self.save_and_publish(metadata):
                    processed.append(metadata)
                else:
                    errors += 1

            except Exception as e:
                logger.error(f"Error processing video: {e}")
                errors += 1
                continue

        logger.info(
            f"Batch complete: {len(processed)} processed, "
            f"{skipped_duplicate} duplicates, "
            f"{skipped_no_match} no IP match, "
            f"{errors} errors"
        )

        return processed
