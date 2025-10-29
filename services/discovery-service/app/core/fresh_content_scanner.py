"""
Fresh Content Scanner - Tier 1 Discovery

Scans HIGH priority IPs for content published in last 24-48 hours.
Ensures trending/viral content is caught immediately.

Cost: 20% of daily quota (~2,000 units)
Coverage: HIGH priority IPs scanned every 2 days
"""

import logging
from datetime import datetime, timedelta, timezone

from .ip_loader import IPTargetManager
from .video_processor import VideoProcessor
from .youtube_client import YouTubeClient

logger = logging.getLogger(__name__)


class FreshContentScanner:
    """
    Scanner for fresh content from high-priority IPs.

    Strategy:
    - Scan HIGH priority IPs only
    - Search for content from last 24-48 hours
    - Use top 2 keywords per IP (most effective)
    - Rotate HIGH IPs across 2 groups (A/B) to stay within quota
    """

    def __init__(
        self,
        youtube_client: YouTubeClient,
        video_processor: VideoProcessor,
        ip_manager: IPTargetManager,
    ):
        """
        Initialize fresh content scanner.

        Args:
            youtube_client: YouTube API client
            video_processor: Video processing operations
            ip_manager: IP target manager
        """
        self.youtube = youtube_client
        self.processor = video_processor
        self.ip_manager = ip_manager

    def scan(
        self, max_quota: int = 2_000, lookback_hours: int = 24
    ) -> dict:
        """
        Scan for fresh content from high-priority IPs.

        Args:
            max_quota: Maximum quota to use (default: 2,000 units = 20% of daily quota)
            lookback_hours: How far back to search (default: 24 hours)

        Returns:
            Stats dict with videos discovered and quota used
        """
        logger.info(
            f"Starting fresh content scan (max_quota={max_quota}, lookback={lookback_hours}h)"
        )

        # Get HIGH priority IPs
        high_priority_ips = self.ip_manager.get_high_priority_targets()

        if not high_priority_ips:
            logger.warning("No HIGH priority IPs found!")
            return {
                "videos_discovered": 0,
                "quota_used": 0,
                "ips_scanned": 0,
                "keywords_scanned": 0,
            }

        # Calculate time window
        now = datetime.now(timezone.utc)
        published_after = now - timedelta(hours=lookback_hours)

        # Format for YouTube API
        after_str = published_after.isoformat().replace("+00:00", "Z")

        # Track stats
        videos_discovered = []
        quota_used = 0
        keywords_scanned = 0
        unique_channels = set()  # Track unique channel IDs

        # Determine which IPs to scan today (A/B rotation to stay within quota)
        ips_to_scan = self._select_ips_for_today(high_priority_ips, max_quota)

        logger.info(
            f"Scanning {len(ips_to_scan)} HIGH priority IPs for content from last {lookback_hours}h"
        )

        # Scan each IP
        for ip_target in ips_to_scan:
            # Use top 2 keywords (most effective)
            keywords_to_scan = ip_target.keywords[:2]

            for keyword in keywords_to_scan:
                # Check quota limit
                if quota_used + 100 > max_quota:
                    logger.info("Fresh content scan quota exhausted")
                    break

                try:
                    # Search for fresh content
                    results = self.youtube.search_videos(
                        query=keyword,
                        max_results=50,
                        order="date",  # Most recent first
                        published_after=after_str,
                    )

                    quota_used += 100
                    keywords_scanned += 1

                    # Process results
                    for video in results:
                        metadata = self.processor.extract_metadata(video)

                        # Skip duplicates
                        if self.processor.is_duplicate(metadata.video_id):
                            continue

                        # Tag with matched IP
                        metadata.matched_ips = [ip_target.name]

                        # Save and publish
                        if self.processor.save_and_publish(metadata):
                            videos_discovered.append(metadata)
                            unique_channels.add(metadata.channel_id)  # Track channel

                            # Update channel profile
                            try:
                                from .channel_tracker import ChannelTracker

                                # Get channel tracker from processor's Firestore client
                                channel_tracker = ChannelTracker(
                                    self.processor.firestore
                                )
                                channel_tracker.get_or_create_profile(
                                    channel_id=metadata.channel_id,
                                    channel_title=metadata.channel_title,
                                )
                                channel_tracker.increment_video_count(
                                    metadata.channel_id, metadata.published_at
                                )
                            except Exception as e:
                                logger.warning(f"Failed to update channel: {e}")

                    logger.info(
                        f"Keyword '{keyword}' ({ip_target.name}): "
                        f"{len([v for v in videos_discovered if keyword.lower() in v.title.lower()])} videos"
                    )

                except Exception as e:
                    logger.error(f"Error scanning keyword '{keyword}': {e}")
                    continue

            # Check if we exhausted quota
            if quota_used + 100 > max_quota:
                break

        stats = {
            "videos_discovered": len(videos_discovered),
            "quota_used": quota_used,
            "ips_scanned": len(ips_to_scan),
            "keywords_scanned": keywords_scanned,
            "channels_tracked": len(unique_channels),  # Add channel count
            "lookback_hours": lookback_hours,
        }

        logger.info(
            f"Fresh content scan complete: {stats['videos_discovered']} videos, "
            f"{stats['quota_used']} quota units"
        )

        return stats

    def _select_ips_for_today(self, high_priority_ips: list, max_quota: int) -> list:
        """
        Select which HIGH priority IPs to scan today based on A/B rotation.

        Strategy:
        - If we can afford all IPs: scan all
        - Otherwise: rotate between Group A (odd days) and Group B (even days)

        Args:
            high_priority_ips: List of HIGH priority IP targets
            max_quota: Maximum quota available

        Returns:
            List of IP targets to scan today
        """
        # Calculate how many IPs we can afford
        # Each IP scans 2 keywords × 100 units = 200 units
        max_ips = max_quota // 200

        # If we can afford all, scan all
        if len(high_priority_ips) <= max_ips:
            logger.info(f"Scanning all {len(high_priority_ips)} HIGH priority IPs")
            return high_priority_ips

        # Otherwise, use A/B rotation based on day of month
        today = datetime.now(timezone.utc).day
        is_even_day = today % 2 == 0

        # Split IPs into two groups
        group_a = high_priority_ips[::2]  # Even indices (0, 2, 4, ...)
        group_b = high_priority_ips[1::2]  # Odd indices (1, 3, 5, ...)

        selected_group = group_b if is_even_day else group_a

        # Limit to max affordable
        selected = selected_group[:max_ips]

        logger.info(
            f"A/B rotation (day {today}, {'B' if is_even_day else 'A'}): "
            f"scanning {len(selected)}/{len(high_priority_ips)} HIGH priority IPs"
        )

        return selected

    def get_trending_keywords(self, limit: int = 10) -> list[tuple[str, str]]:
        """
        Get trending keywords from HIGH priority IPs.

        Returns top keywords optimized for catching viral content.

        Args:
            limit: Maximum number of keywords

        Returns:
            List of (keyword, ip_name) tuples
        """
        high_priority_ips = self.ip_manager.get_high_priority_targets()

        keywords = []
        for ip in high_priority_ips:
            # For trending, use viral-focused keywords if available
            viral_keywords = [
                kw
                for kw in ip.keywords
                if any(term in kw.lower() for term in ["viral", "trending", "trailer"])
            ]

            if viral_keywords:
                keywords.append((viral_keywords[0], ip.name))
            elif ip.keywords:
                # Fallback to first keyword
                keywords.append((ip.keywords[0], ip.name))

            if len(keywords) >= limit:
                break

        return keywords[:limit]
