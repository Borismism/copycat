"""
Discovery Engine - 3-Tier Intelligent Orchestrator

Scalable architecture for 100+ IPs:
  Tier 1 (20%): Fresh Content - HIGH priority IPs, last 24h
  Tier 2 (60%): Channel Tracking - Known channels, adaptive frequency
  Tier 3 (20%): Deep Keyword Rotation - Priority-based comprehensive scan

Capacity: 85 IPs with 10k quota, 850 IPs with 100k quota
"""

import logging
from datetime import datetime, timezone

from ..models import DiscoveryStats
from .channel_tracker import ChannelTracker
from .fresh_content_scanner import FreshContentScanner
from .ip_loader import IPTargetManager
from .keyword_tracker import KeywordTracker
from .quota_manager import QuotaManager
from .video_processor import VideoProcessor
from .youtube_client import YouTubeClient

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    """
    3-Tier Intelligent Discovery Orchestrator.

    Tier 1 (20%): Fresh content from HIGH priority IPs
    Tier 2 (60%): Channel tracking (most cost-effective)
    Tier 3 (20%): Priority-based keyword rotation
    """

    def __init__(
        self,
        youtube_client: YouTubeClient,
        video_processor: VideoProcessor,
        channel_tracker: ChannelTracker,
        quota_manager: QuotaManager,
        keyword_tracker: KeywordTracker,
    ):
        self.youtube = youtube_client
        self.processor = video_processor
        self.channels = channel_tracker
        self.quota = quota_manager
        self.keywords = keyword_tracker

        # Initialize IP manager and fresh content scanner
        self.ip_manager = IPTargetManager()
        self.fresh_scanner = FreshContentScanner(
            youtube_client=youtube_client,
            video_processor=video_processor,
            ip_manager=self.ip_manager,
        )

        # Sync keyword priorities from IP targets
        try:
            sync_stats = self.keywords.sync_keywords_from_ip_targets(self.ip_manager)
            logger.info(f"Synced keywords: {sync_stats}")
        except Exception as e:
            logger.warning(f"Failed to sync keyword priorities: {e}")

        logger.info("DiscoveryEngine initialized (3-tier strategy)")

    async def discover(self, max_quota: int = 100) -> DiscoveryStats:
        """
        Execute 4-tier intelligent discovery + video rescanning.

        Args:
            max_quota: Maximum quota units (default: 100)

        Returns:
            Aggregated discovery statistics
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"=== 4-Tier Discovery (quota={max_quota}) ===")

        # Calculate tier budgets - PRIORITIZE NEW CHANNEL DISCOVERY
        tier1_quota = int(max_quota * 0.25)  # Fresh: 25% - NEW CHANNELS
        tier2_quota = int(max_quota * 0.10)  # Deep Scan: 10% - existing channels
        tier3_quota = int(max_quota * 0.10)  # Channel monitoring: 10%
        tier4_quota = int(max_quota * 0.45)  # Keywords: 45% - NEW CHANNELS (biggest!)
        rescan_quota = int(max_quota * 0.10)  # Rescan: 10%

        tier_stats = {}

        # TIER 1: Fresh Content Scanner
        logger.info(f"TIER 1: Fresh Content (quota={tier1_quota})")
        try:
            fresh_stats = self.fresh_scanner.scan(
                max_quota=tier1_quota, lookback_hours=24
            )
            tier_stats["tier1"] = fresh_stats
            self.quota.record_usage("search", fresh_stats["keywords_scanned"])
            logger.info(
                f"Tier 1: {fresh_stats['videos_discovered']} videos, {fresh_stats['quota_used']} quota"
            )
        except Exception as e:
            logger.error(f"Tier 1 failed: {e}")
            tier_stats["tier1"] = {"videos_discovered": 0, "quota_used": 0}

        # TIER 2: Deep Channel Scan (find ALL matching videos in channel history)
        logger.info(f"TIER 2: Deep Channel Scan (quota={tier2_quota})")
        tier2_stats = self._deep_scan_channels(tier2_quota)
        tier_stats["tier2"] = tier2_stats
        logger.info(
            f"Tier 2: {tier2_stats['videos_discovered']} videos, {tier2_stats['quota_used']} quota, {tier2_stats['channels_deep_scanned']} channels"
        )

        # TIER 3: Channel Tracking (regular monitoring)
        logger.info(f"TIER 3: Channel Tracking (quota={tier3_quota})")
        tier3_stats = self._scan_channels(tier3_quota)
        tier_stats["tier3"] = tier3_stats
        logger.info(
            f"Tier 3: {tier3_stats['videos_discovered']} videos, {tier3_stats['quota_used']} quota"
        )

        # TIER 4: Priority-Based Keyword Rotation
        logger.info(f"TIER 4: Keyword Rotation (quota={tier4_quota})")
        tier4_stats = self._scan_keywords(tier4_quota)
        tier_stats["tier4"] = tier4_stats
        logger.info(
            f"Tier 4: {tier4_stats['videos_discovered']} videos, {tier4_stats['quota_used']} quota"
        )

        # TIER 5: Video Rescanning (detect trending)
        logger.info(f"TIER 5: Video Rescanning (quota={rescan_quota})")
        tier5_stats = self._rescan_videos(rescan_quota)
        tier_stats["tier5"] = tier5_stats
        logger.info(
            f"Tier 5: {tier5_stats['videos_rescanned']} videos rescanned, {tier5_stats['trending_count']} trending"
        )

        # Aggregate stats
        total_videos = sum(t.get("videos_discovered", 0) for t in tier_stats.values())
        total_quota = sum(t.get("quota_used", 0) for t in tier_stats.values())
        # Sum channels from all tiers (tier1, tier2, tier3)
        total_channels = (
            tier_stats.get("tier1", {}).get("channels_tracked", 0)
            + tier_stats.get("tier2", {}).get("channels_scanned", 0)  # tier2 uses "channels_scanned"
            + tier_stats.get("tier3", {}).get("channels_tracked", 0)
        )
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        stats = DiscoveryStats(
            videos_discovered=total_videos,
            videos_with_ip_match=total_videos,
            videos_skipped_duplicate=0,
            quota_used=total_quota,
            channels_tracked=total_channels,
            duration_seconds=duration,
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            f"=== Complete: {total_videos} videos, {total_quota}/{max_quota} quota ({total_quota/max_quota*100:.1f}%) ==="
        )

        self._save_metrics(stats, tier_stats)
        return stats

    def _deep_scan_channels(self, max_quota: int) -> dict:
        """
        Tier 2: Deep scan channels to find ALL videos in their history.

        EFFICIENT APPROACH:
        - Get ALL channel uploads via pagination (cheap: 3-10 units)
        - Filter videos locally using IP keyword matching
        - No expensive search API calls (100 units each)

        Quota cost per channel (scanning last 100 videos):
        - Channel with 50 videos: 3 units
        - Channel with 100+ videos: 5 units

        vs. Keyword search: 1,200 units per channel (240x more expensive!)
        """
        channels_deep_scanned = 0
        videos_discovered = 0
        quota_used = 0

        try:
            # Get channels that need deep scanning
            channels = self.channels.get_channels_needing_deep_scan(limit=100)

            if not channels:
                logger.info("No channels need deep scanning")
                return {
                    "channels_deep_scanned": 0,
                    "videos_discovered": 0,
                    "quota_used": 0,
                }

            logger.info(f"Found {len(channels)} channels needing deep scan")

            for channel in channels:
                # Estimate quota cost: 3 base + 2 for pagination (100 videos max)
                estimated_cost = 5

                if quota_used + estimated_cost > max_quota:
                    logger.info(f"Quota limit reached, stopping deep scan")
                    break

                if not self.quota.can_afford("channel_details", 3):
                    logger.info(f"Global quota exhausted, stopping deep scan")
                    break

                try:
                    # For first-time deep scan, get more videos to find historical content
                    # For rescans, only need recent uploads
                    is_first_scan = channel.last_upload_date is None
                    max_vids = 200 if is_first_scan else 50

                    logger.info(
                        f"{'FIRST' if is_first_scan else 'RE'}scanning channel {channel.channel_id} ({channel.channel_title}) "
                        f"- fetching up to {max_vids} uploads"
                    )

                    # Get channel uploads
                    videos = self.youtube.get_channel_uploads(
                        channel_id=channel.channel_id,
                        max_results=max_vids,
                    )

                    # Calculate actual quota cost
                    # 1 unit for channel lookup + 1 for playlist + batches for video details
                    playlist_fetches = (len(videos) // 50) + (1 if len(videos) % 50 else 0) if videos else 1
                    details_fetches = (len(videos) // 50) + (1 if len(videos) % 50 else 0) if videos else 0
                    scan_quota = 1 + playlist_fetches + details_fetches  # channel + playlist pages + video details

                    quota_used += scan_quota
                    self.quota.record_usage("channel_details", 1)
                    self.quota.record_usage("playlist_items", playlist_fetches)
                    self.quota.record_usage("video_details", details_fetches)

                    channels_deep_scanned += 1

                    # Filter out old videos we've already processed
                    # Only scan videos published AFTER our last scan of this channel
                    original_count = len(videos)
                    if videos and channel.last_upload_date:
                        from datetime import datetime
                        videos = [
                            v for v in videos
                            if v.get("snippet", {}).get("publishedAt")
                        ]
                        # Parse published dates and filter
                        new_videos = []
                        for v in videos:
                            try:
                                pub_date_str = v["snippet"]["publishedAt"]
                                # Remove 'Z' and parse
                                pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                                if pub_date > channel.last_upload_date:
                                    new_videos.append(v)
                            except Exception:
                                new_videos.append(v)  # Include if can't parse (safe fallback)

                        if new_videos:
                            logger.info(
                                f"Channel {channel.channel_id}: Filtered {original_count} → {len(new_videos)} new videos "
                                f"(after {channel.last_upload_date.date()})"
                            )
                        videos = new_videos

                    # Process videos - IP matching done locally (FREE!)
                    if videos:
                        results = self.processor.process_batch(
                            videos,
                            skip_duplicates=True,
                            skip_no_ip_match=True  # Only save videos matching our IPs
                        )
                        videos_discovered += len(results)

                        # Update channel with latest upload
                        latest = max((v.published_at for v in results), default=None) if results else None
                        self.channels.update_after_scan(channel.channel_id, len(results) > 0, latest)

                        logger.info(
                            f"Channel {channel.channel_id}: Found {len(results)} matching videos "
                            f"out of {len(videos)} new uploads (total fetched: {original_count})"
                        )

                    # Mark deep scan complete
                    self.channels.mark_deep_scan_complete(channel.channel_id)

                    logger.info(
                        f"Channel {channel.channel_id}: Deep scan complete, "
                        f"quota used: {scan_quota} units (scanned {len(videos)} videos)"
                    )

                except Exception as e:
                    logger.error(f"Deep scan failed for channel {channel.channel_id}: {e}")
                    # Mark as complete anyway to avoid retry loops
                    self.channels.mark_deep_scan_complete(channel.channel_id)
                    continue

        except Exception as e:
            logger.error(f"Tier 2 deep scan error: {e}")

        return {
            "channels_deep_scanned": channels_deep_scanned,
            "videos_discovered": videos_discovered,
            "quota_used": quota_used,
        }

    def _scan_channels(self, max_quota: int) -> dict:
        """Tier 3: Scan channels with history of violations (regular monitoring)."""
        channels_scanned = 0
        videos_discovered = 0
        quota_used = 0

        try:
            channels = self.channels.get_channels_due_for_scan(limit=5000)

            for channel in channels:
                if quota_used + 3 > max_quota:
                    break
                if not self.quota.can_afford("channel_details", 3):
                    break

                try:
                    videos = self.youtube.get_channel_uploads(
                        channel.channel_id, max_results=20
                    )
                    quota_used += 3
                    self.quota.record_usage("channel_details", 3)
                    channels_scanned += 1

                    results = self.processor.process_batch(videos, skip_no_ip_match=True)
                    videos_discovered += len(results)

                    latest = max((v.published_at for v in results), default=None) if results else None
                    self.channels.update_after_scan(channel.channel_id, len(results) > 0, latest)

                except Exception as e:
                    logger.error(f"Channel {channel.channel_id} scan failed: {e}")

        except Exception as e:
            logger.error(f"Tier 2 error: {e}")

        return {
            "channels_scanned": channels_scanned,
            "videos_discovered": videos_discovered,
            "quota_used": quota_used,
        }

    def _scan_keywords(self, max_quota: int) -> dict:
        """Tier 3: Priority-based keyword rotation."""
        keywords_scanned = 0
        videos_discovered = 0
        quota_used = 0
        unique_channels = set()  # Track unique channel IDs

        try:
            keywords_due = self.keywords.get_keywords_due_for_scan(limit=100)

            for keyword, priority, ip_name in keywords_due:
                if quota_used + 101 > max_quota:  # search (100) + video_details (1)
                    break
                if not self.quota.can_afford("search", 1):
                    break

                try:
                    # Get time window - use shorter window to find more recent content
                    after, before = self.keywords.get_next_scan_window(keyword, window_days=7)
                    after_str = after.isoformat().replace("+00:00", "Z")
                    before_str = before.isoformat().replace("+00:00", "Z")

                    # Search - use date to find newest content first
                    results = self.youtube.search_videos(
                        query=keyword,
                        max_results=50,
                        order="date",  # Get newest videos (more likely to be new channels)
                        published_after=after_str,
                        published_before=before_str,
                    )
                    quota_used += 100
                    self.quota.record_usage("search", 1)

                    # Enrich with video details
                    if results:
                        video_ids = [
                            v['id']['videoId'] if isinstance(v.get('id'), dict) else v['id']
                            for v in results
                        ]
                        results = self.youtube.get_video_details(video_ids)
                        quota_used += 1
                        self.quota.record_usage("video_details", 1)

                    keywords_scanned += 1

                    # Process results
                    found = 0
                    for video in results:
                        metadata = self.processor.extract_metadata(video)
                        if self.processor.is_duplicate(metadata.video_id):
                            continue

                        # Set IP name from keyword mapping
                        metadata.matched_ips = [ip_name]

                        if self.processor.save_and_publish(metadata):
                            videos_discovered += 1
                            found += 1
                            unique_channels.add(metadata.channel_id)  # Track channel

                            # Update channel
                            try:
                                self.channels.get_or_create_profile(
                                    metadata.channel_id, metadata.channel_title
                                )
                                self.channels.increment_video_count(
                                    metadata.channel_id, metadata.published_at
                                )
                            except Exception:
                                pass

                    self.keywords.record_results(keyword, found)

                except Exception as e:
                    logger.error(f"Keyword '{keyword}' scan failed: {e}")

        except Exception as e:
            logger.error(f"Tier 3 error: {e}")

        return {
            "keywords_scanned": keywords_scanned,
            "videos_discovered": videos_discovered,
            "quota_used": quota_used,
            "channels_tracked": len(unique_channels),  # Add channel count
        }

    def _rescan_videos(self, max_quota: int) -> dict:
        """Tier 4: Rescan low-view videos to detect trending."""
        from .video_rescanner import VideoRescanner

        rescanner = VideoRescanner(self.processor.firestore)
        videos_rescanned = 0
        trending_count = 0
        quota_used = 0

        try:
            # Get videos to rescan (recently discovered, low views)
            max_videos = max_quota  # 1 quota unit per video
            video_ids = rescanner.get_videos_to_rescan(
                max_age_hours=72,  # Last 3 days
                max_views=10_000,  # Under 10k views
                limit=max_videos
            )

            if not video_ids:
                logger.info("No videos to rescan")
                return {
                    "videos_rescanned": 0,
                    "trending_count": 0,
                    "quota_used": 0,
                }

            # Rescan in batches of 50
            for i in range(0, len(video_ids), 50):
                batch = video_ids[i:i+50]
                if quota_used + 1 > max_quota:
                    break
                if not self.quota.can_afford("video_details", 1):
                    break

                results = rescanner.rescan_batch(batch, self.youtube)
                videos_rescanned += len(results)
                trending_count += sum(1 for r in results.values() if r.get("is_trending"))
                quota_used += 1
                self.quota.record_usage("video_details", 1)

        except Exception as e:
            logger.error(f"Tier 4 error: {e}")

        return {
            "videos_rescanned": videos_rescanned,
            "trending_count": trending_count,
            "quota_used": quota_used,
        }

    def _save_metrics(self, stats: DiscoveryStats, tier_stats: dict):
        """Save discovery metrics to Firestore."""
        try:
            if not hasattr(self.processor, "firestore"):
                return

            self.processor.firestore.collection("discovery_metrics").add({
                "timestamp": stats.timestamp,
                "videos_discovered": stats.videos_discovered,
                "quota_used": stats.quota_used,
                "channels_tracked": stats.channels_tracked,
                "duration_seconds": stats.duration_seconds,
                "tier_breakdown": tier_stats,
            })

        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
