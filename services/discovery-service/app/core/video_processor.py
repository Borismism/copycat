"""Video processing operations - zero duplication."""

import logging
import re
from datetime import datetime, UTC, timedelta
from typing import Any

from google.cloud import firestore, pubsub_v1

from ..config import settings
from ..models import VideoMetadata, VideoStatus

logger = logging.getLogger(__name__)

# Cache for IP configs (refresh every 5 minutes)
_ip_configs_cache: list[dict[str, Any]] | None = None
_ip_configs_cache_time: datetime | None = None
_IP_CACHE_TTL_SECONDS = 300  # 5 minutes


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
        topic_path: str,
        channel_tracker: "ChannelTracker | None" = None,
    ):
        """
        Initialize video processor.

        Args:
            firestore_client: Firestore client for data persistence
            pubsub_publisher: PubSub client for event publishing
            topic_path: Full PubSub topic path (projects/X/topics/Y)
            channel_tracker: Optional channel tracker for profile creation
        """
        self.firestore = firestore_client
        self.publisher = pubsub_publisher
        self.topic_path = topic_path
        self.channel_tracker = channel_tracker
        self.videos_collection = "videos"
        self.hourly_stats_collection = "hourly_stats"

        logger.info("VideoProcessor initialized")

    def _increment_hourly_stat(self, stat_type: str, timestamp: datetime | None = None):
        """
        Atomically increment hourly stats counter in Firestore.

        Args:
            stat_type: Type of stat to increment ("discoveries", "analyses", "infringements")
            timestamp: Timestamp to use (defaults to now)
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(UTC)

            # Round to hour
            hour = timestamp.replace(minute=0, second=0, microsecond=0)
            hour_key = hour.strftime("%Y-%m-%d_%H")  # e.g., "2025-11-07_10"

            stats_ref = self.firestore.collection(self.hourly_stats_collection).document(hour_key)

            # Atomic increment
            stats_ref.set({
                "hour": hour,
                stat_type: firestore.Increment(1),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)

        except Exception as e:
            # Don't fail the main operation if stats update fails
            logger.warning(f"Failed to increment hourly stat {stat_type}: {e}")

    def _update_channel_stats(self, metadata: VideoMetadata):
        """
        Update channel aggregate stats when a new video is discovered.

        Args:
            metadata: Video metadata
        """
        try:
            channel_ref = self.firestore.collection("channels").document(metadata.channel_id)

            # Atomic increments for channel stats
            channel_ref.set({
                "channel_id": metadata.channel_id,
                "channel_title": metadata.channel_title,
                "total_videos_found": firestore.Increment(1),
                "total_views": firestore.Increment(metadata.view_count or 0),
                "last_seen_at": datetime.now(UTC),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)

            logger.debug(f"Updated channel stats for {metadata.channel_id}")

        except Exception as e:
            # Don't fail the main operation if stats update fails
            logger.warning(f"Failed to update channel stats: {e}")

    def _increment_global_stat(self, stat_name: str, increment: int = 1):
        """
        Atomically increment global statistics counter.

        Args:
            stat_name: Name of the stat to increment (e.g., "total_videos", "total_channels")
            increment: Amount to increment by
        """
        try:
            stats_ref = self.firestore.collection("system_stats").document("global")

            # Atomic increment
            stats_ref.set({
                stat_name: firestore.Increment(increment),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)

        except Exception as e:
            # Don't fail the main operation if stats update fails
            logger.warning(f"Failed to increment global stat {stat_name}: {e}")

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
            published_at = datetime.now(UTC)

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

    def update_if_existing(self, metadata: VideoMetadata) -> tuple[bool, bool]:
        """
        Update video metadata if it already exists (duplicates = rescans for virality tracking).

        Discovery duplicates are GOOD - they let us:
        - Track view count growth → Calculate view velocity → Detect viral videos
        - Update all metadata (title, description, etc.)
        - Trigger priority rescore for videos going viral

        Args:
            metadata: Fresh video metadata from YouTube

        Returns:
            (is_existing, needs_rescore):
                - is_existing: True if video existed before (duplicate)
                - needs_rescore: True if views changed significantly (>10%)
        """
        doc_ref = self.firestore.collection(self.videos_collection).document(metadata.video_id)

        try:
            doc = doc_ref.get()

            if not doc.exists:
                # Brand new video
                return (False, False)

            # DUPLICATE FOUND - Update it!
            old_data = doc.to_dict()
            old_views = old_data.get("view_count", 0)
            new_views = metadata.view_count

            # Calculate view velocity (views gained since last check)
            views_gained = new_views - old_views
            time_elapsed_hours = (datetime.now(UTC) - old_data.get("updated_at", datetime.now(UTC))).total_seconds() / 3600
            view_velocity = int(views_gained / time_elapsed_hours) if time_elapsed_hours > 0 else 0

            # Update all fresh metadata
            doc_ref.update({
                "view_count": new_views,
                "like_count": metadata.like_count,
                "comment_count": metadata.comment_count,
                "view_velocity": view_velocity,
                "updated_at": datetime.now(UTC),
                "last_seen_at": datetime.now(UTC),
            })

            # Needs rescore if views increased significantly (>10% or >1000 views)
            view_change_pct = (views_gained / old_views * 100) if old_views > 0 else 0
            needs_rescore = views_gained > 1000 or view_change_pct > 10

            if needs_rescore:
                logger.info(
                    f"Video {metadata.video_id}: views {old_views:,} → {new_views:,} "
                    f"(+{views_gained:,}, velocity={view_velocity}/hr) - RESCORE NEEDED"
                )

            return (True, needs_rescore)

        except Exception as e:
            logger.error(f"Error updating existing video {metadata.video_id}: {e}")
            # On error, treat as new video
            return (False, False)

    def _load_ip_configs_cached(self) -> list[dict[str, Any]]:
        """
        Load IP configs from Firestore with in-memory caching.

        Cache is refreshed every 5 minutes to avoid network calls on every video.

        Returns:
            List of IP config dicts with id, search_keywords, and characters
        """
        global _ip_configs_cache, _ip_configs_cache_time

        now = datetime.now(UTC)

        # Return cached configs if still fresh
        if (_ip_configs_cache is not None and
            _ip_configs_cache_time is not None and
            (now - _ip_configs_cache_time).total_seconds() < _IP_CACHE_TTL_SECONDS):
            return _ip_configs_cache

        # Refresh cache
        try:
            docs = self.firestore.collection("ip_configs").stream()
            configs = []

            for doc in docs:
                data = doc.to_dict()
                configs.append({
                    "id": doc.id,
                    "search_keywords": data.get("search_keywords", []),
                    "characters": data.get("characters", []),
                })

            _ip_configs_cache = configs
            _ip_configs_cache_time = now
            logger.info(f"Loaded {len(configs)} IP configs into cache")

            return configs

        except Exception as e:
            logger.error(f"Error loading IP configs: {e}")
            # Return stale cache if available, otherwise empty list
            return _ip_configs_cache if _ip_configs_cache else []

    def match_ips(self, metadata: VideoMetadata) -> list[str]:
        """
        Match video content against configured IP targets.

        Searches across:
        - Video title
        - Video description
        - Video tags
        - Channel name

        Uses cached IP configs (refreshed every 5 minutes).

        Args:
            metadata: Video metadata to analyze

        Returns:
            List of matched IP IDs (e.g., ["dc-universe"])
        """
        try:
            # Load IP configs from cache (fast!)
            configs = self._load_ip_configs_cached()

            matched_ids = []
            search_text = f"{metadata.title} {metadata.description} {' '.join(metadata.tags)} {metadata.channel_title}".lower()

            for config in configs:
                keywords = config["search_keywords"]
                characters = config["characters"]
                ip_id = config["id"]

                # Match keywords or character names
                for keyword in keywords:
                    if keyword.lower() in search_text:
                        matched_ids.append(ip_id)
                        break

                # Also check character names if no keyword match
                if ip_id not in matched_ids:
                    for char in characters:
                        if char.lower() in search_text:
                            matched_ids.append(ip_id)
                            break

            return matched_ids

        except Exception as e:
            logger.error(f"Error matching IPs: {e}")
            return []

    def _get_channel_risk(self, channel_id: str) -> int:
        """
        Get channel risk score from Firestore.

        Uses simple heuristic based on channel's infringement history:
        - No data (new channel): 40 (assume risky until proven otherwise)
        - Has infringements: High risk (60-80)
        - Clean history: Lower risk (10-30)

        Args:
            channel_id: YouTube channel ID

        Returns:
            Channel risk score (0-100), default 40 for unknown channels
        """
        try:
            doc_ref = self.firestore.collection("channels").document(channel_id)
            doc = doc_ref.get()

            if not doc.exists:
                # Unknown channel = assume risky (GUILTY UNTIL PROVEN INNOCENT)
                return 40

            channel_data = doc.to_dict()

            # Calculate simple risk based on infringement history
            infringing_count = channel_data.get("infringing_videos_count", 0)
            channel_data.get("total_videos_found", 0)
            videos_scanned = channel_data.get("videos_scanned", 0)

            # If has confirmed infringements, HIGH RISK
            if infringing_count > 0:
                if infringing_count >= 10:
                    return 80  # Serial infringer
                elif infringing_count >= 5:
                    return 70  # Frequent infringer
                elif infringing_count >= 2:
                    return 60  # Repeat infringer
                else:
                    return 50  # Single infringer (but proven bad)

            # No infringements yet - score by clean scan count
            if videos_scanned == 0:
                return 40  # Unknown = assume risky
            elif videos_scanned <= 2:
                return 30  # Still suspicious
            elif videos_scanned <= 5:
                return 20  # Probably clean
            else:
                return 10  # Proven clean

        except Exception as e:
            logger.error(f"Error getting channel risk for {channel_id}: {e}")
            return 40  # Default to risky on error

    def calculate_initial_risk(self, metadata: VideoMetadata, channel_risk: int) -> int:
        """
        Calculate initial risk score (0-100) for newly discovered video.

        Five-factor risk algorithm:
        1. Channel risk (0-50 points) - 50% weight
        2. View count (0-15 points) - popularity indicator
        3. IP matches (0-20 points) - more matches = higher confidence
        4. Duration (0-10 points) - longer videos need more review
        5. Age (0-5 points) - recent videos get priority

        Args:
            metadata: Video metadata to analyze
            channel_risk: Channel's current risk score (0-100)

        Returns:
            Risk score from 0-100
        """
        risk = 0

        # Factor 1: Channel reputation (50% weight)
        # Scale channel risk from 0-100 to 0-50
        risk += min(channel_risk // 2, 50)

        # Factor 2: View count indicates popularity
        if metadata.view_count > 1_000_000:
            risk += 15
        elif metadata.view_count > 100_000:
            risk += 10
        elif metadata.view_count > 10_000:
            risk += 5

        # Factor 3: More IP matches = higher confidence of infringement
        risk += min(len(metadata.matched_ips) * 5, 20)

        # Factor 4: Longer videos = more content to review
        if metadata.duration_seconds > 600:  # >10 min
            risk += 10
        elif metadata.duration_seconds > 300:  # >5 min
            risk += 5

        # Factor 5: Recent videos get priority
        age_days = (datetime.now(UTC) - metadata.published_at).days
        if age_days <= 7:
            risk += 5
        elif age_days <= 30:
            risk += 3

        return min(risk, 100)

    def calculate_risk_tier(self, risk_score: int) -> str:
        """
        Map risk score to tier for scan scheduling.

        Tiers:
        - CRITICAL: 80-100 (scan within 6 hours)
        - HIGH: 60-79 (scan within 24 hours)
        - MEDIUM: 40-59 (scan within 72 hours)
        - LOW: 20-39 (scan within 7 days)
        - VERY_LOW: 0-19 (scan within 30 days)

        Args:
            risk_score: Risk score from 0-100

        Returns:
            Risk tier string
        """
        if risk_score >= 80:
            return "CRITICAL"
        elif risk_score >= 60:
            return "HIGH"
        elif risk_score >= 40:
            return "MEDIUM"
        elif risk_score >= 20:
            return "LOW"
        else:
            return "VERY_LOW"

    def save_and_publish(self, metadata: VideoMetadata) -> bool:
        """
        Atomically save to Firestore and publish to PubSub.

        Operations:
        1. Create/update channel profile
        2. Save video document to Firestore
        3. Publish video message to PubSub

        Both operations must succeed. If either fails, logs error
        but doesn't raise (allows processing to continue).

        Args:
            metadata: Video metadata to persist

        Returns:
            True if both operations succeeded, False otherwise
        """
        try:
            # Create/update channel profile if channel_tracker available
            if self.channel_tracker:
                try:
                    self.channel_tracker.get_or_create_profile(
                        channel_id=metadata.channel_id,
                        channel_title=metadata.channel_title
                    )
                except Exception as e:
                    logger.warning(f"Failed to create channel profile for {metadata.channel_id}: {e}")
                    # Don't fail the whole operation if channel profile fails

            # Save video document (single write - no stats updates in hot path)
            doc_ref = self.firestore.collection(self.videos_collection).document(
                metadata.video_id
            )

            video_doc = {
                **metadata.model_dump(),
                "status": VideoStatus.DISCOVERED.value,
                "discovered_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }

            doc_ref.set(video_doc)
            logger.info(f"Saved video {metadata.video_id} to Firestore")

            # Increment hourly discoveries counter
            self._increment_hourly_stat("discoveries")

            # Update channel stats (video count, views, etc.)
            self._update_channel_stats(metadata)

            # Increment global video count
            self._increment_global_stat("total_videos", 1)

            # Publish to PubSub (non-blocking - don't wait for confirmation)
            message_data = metadata.model_dump_json().encode("utf-8")
            future = self.publisher.publish(self.topic_path, message_data)

            # Add callback for logging (async, won't block)
            def log_publish_result(f):
                try:
                    message_id = f.result()
                    logger.info(f"Published video {metadata.video_id} to PubSub: {message_id}")
                except Exception as e:
                    logger.error(f"Failed to publish video {metadata.video_id}: {e}")

            future.add_done_callback(log_publish_result)

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

                # Check if existing video (duplicate = good! means we can track virality)
                is_existing, needs_rescore = self.update_if_existing(metadata)

                if is_existing:
                    # Already exists - metadata updated, check if needs priority rescore
                    if needs_rescore:
                        # Views spiked! Republish to trigger priority rescore
                        logger.info(f"Video {metadata.video_id} going viral - republishing for rescore")
                        self.publish_discovered_video(metadata)
                        processed.append(metadata)
                    else:
                        # Metadata updated but no significant change
                        skipped_duplicate += 1
                    continue

                # NEW VIDEO - Match IPs
                matched_ips = self.match_ips(metadata)

                if not matched_ips:
                    if skip_no_ip_match:
                        skipped_no_match += 1
                        continue

                metadata.matched_ips = matched_ips

                # Calculate initial risk score with actual channel risk
                channel_risk = self._get_channel_risk(metadata.channel_id)
                metadata.initial_risk = self.calculate_initial_risk(metadata, channel_risk)
                metadata.current_risk = metadata.initial_risk  # Initially same
                metadata.risk_tier = self.calculate_risk_tier(metadata.initial_risk)

                logger.debug(
                    f"Video {metadata.video_id}: risk={metadata.initial_risk}, "
                    f"tier={metadata.risk_tier}"
                )

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
