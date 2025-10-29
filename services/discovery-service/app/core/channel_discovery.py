"""Channel-first discovery strategy - most efficient method."""

import logging

from ..models import VideoMetadata
from .channel_tracker import ChannelTracker
from .quota_manager import QuotaManager
from .video_processor import VideoProcessor
from .youtube_client import YouTubeClient

logger = logging.getLogger(__name__)


class ChannelDiscovery:
    """
    Channel-first discovery strategy.

    The MOST EFFICIENT discovery method:
    - Cost: 3 units per channel (vs 100 per search)
    - 30x more efficient than keyword searches
    - Builds on historical channel knowledge
    - Adaptive scan frequency based on tier
    - Targets known infringers

    Discovery flow:
    1. Get channels due for scan (from ChannelTracker)
    2. Fetch recent uploads per channel (YouTube API - 3 units)
    3. Deduplicate against Firestore
    4. Batch process with VideoProcessor
    5. Update channel profile and tier
    6. Track quota usage
    """

    # YouTube API costs for channel discovery
    COST_PER_CHANNEL = 3  # channels.list + playlistItems.list + videos.list

    def __init__(
        self,
        youtube_client: YouTubeClient,
        video_processor: VideoProcessor,
        channel_tracker: ChannelTracker,
        quota_manager: QuotaManager,
    ):
        """
        Initialize channel discovery.

        Args:
            youtube_client: YouTube API client
            video_processor: Video processing operations
            channel_tracker: Channel profiling and tracking
            quota_manager: Quota tracking and enforcement
        """
        self.youtube = youtube_client
        self.video_processor = video_processor
        self.channel_tracker = channel_tracker
        self.quota_manager = quota_manager

        logger.info("ChannelDiscovery initialized")

    def discover_from_channels(
        self, max_channels: int = 50, videos_per_channel: int = 20
    ) -> list[VideoMetadata]:
        """
        Discover videos by scanning channels due for refresh.

        Most efficient discovery method - scans channels with known
        infringement history, adapting frequency based on tier.

        Args:
            max_channels: Maximum channels to scan (default: 50)
            videos_per_channel: Max recent uploads per channel (default: 20)

        Returns:
            List of discovered videos with IP matches
        """
        logger.info(
            f"Starting channel-based discovery "
            f"(max_channels={max_channels}, videos_per_channel={videos_per_channel})"
        )

        # Get channels due for scanning (sorted by tier priority)
        channels = self.channel_tracker.get_channels_due_for_scan(limit=max_channels)

        if not channels:
            logger.info("No channels due for scanning")
            return []

        logger.info(
            f"Found {len(channels)} channels due for scan "
            f"(tiers: {self._count_by_tier(channels)})"
        )

        discovered_videos = []
        channels_scanned = 0
        quota_used_total = 0

        for channel in channels:
            # Check quota before scanning
            if not self.quota_manager.can_afford("channel_details", count=1):
                logger.warning(
                    f"Insufficient quota to scan more channels "
                    f"(scanned: {channels_scanned}/{len(channels)})"
                )
                break

            try:
                # Fetch recent uploads (cost: 3 units)
                videos = self.youtube.get_channel_uploads(
                    channel.channel_id, max_results=videos_per_channel
                )

                # Record quota usage
                self.quota_manager.record_usage("channel_details", count=1)
                quota_used_total += self.COST_PER_CHANNEL

                if not videos:
                    logger.debug(f"No recent uploads for channel {channel.channel_id}")
                    channels_scanned += 1
                    continue

                logger.info(
                    f"Fetched {len(videos)} recent uploads from "
                    f"{channel.channel_title} (tier: {channel.tier})"
                )

                # Process videos (dedup, IP match, save, publish)
                processed = self.video_processor.process_batch(
                    videos, skip_duplicates=True, skip_no_ip_match=True
                )

                discovered_videos.extend(processed)

                # Update channel profile
                had_infringement = len(processed) > 0
                self.channel_tracker.update_after_scan(
                    channel.channel_id, had_infringement
                )

                channels_scanned += 1

                logger.info(
                    f"Channel {channel.channel_title}: "
                    f"{len(processed)} videos with IP matches"
                )

            except Exception as e:
                logger.error(f"Error scanning channel {channel.channel_id}: {e}")
                continue

        logger.info(
            f"Channel-based discovery complete: "
            f"{len(discovered_videos)} videos discovered from "
            f"{channels_scanned} channels (quota: {quota_used_total} units)"
        )

        return discovered_videos

    def _count_by_tier(self, channels: list) -> dict:
        """
        Count channels by tier for logging.

        Args:
            channels: List of ChannelProfile objects

        Returns:
            Dictionary with tier counts
        """
        counts = {}
        for channel in channels:
            tier = channel.tier
            counts[tier] = counts.get(tier, 0) + 1
        return counts

    def get_efficiency_metrics(self) -> dict:
        """
        Get channel discovery efficiency metrics.

        Returns:
            Dictionary with efficiency stats:
            - cost_per_channel: Units per channel (always 3)
            - cost_per_video: Avg units per discovered video
            - vs_search_efficiency: How much more efficient vs search
        """
        return {
            "cost_per_channel": self.COST_PER_CHANNEL,
            "cost_per_video_estimate": 0.15,  # Assuming ~20 videos/channel
            "vs_search_cost": 100,  # Search cost
            "efficiency_multiplier": 33.3,  # 100/3 = 33x more efficient
            "method": "channel_tracking",
        }
