"""Firestore client for querying video and channel data."""

from datetime import datetime, timedelta

from google.cloud import firestore

from app.core.config import settings
from app.models import ChannelProfile, ChannelStats, ChannelTier, VideoMetadata, VideoStatus


class FirestoreClient:
    """Client for Firestore operations."""

    def __init__(self):
        self.db = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database
        )
        self.videos_collection = self.db.collection("videos")
        self.channels_collection = self.db.collection("channels")

    async def get_video(self, video_id: str) -> VideoMetadata | None:
        """Get a single video by ID."""
        doc = self.videos_collection.document(video_id).get()
        if not doc.exists:
            return None

        data = doc.to_dict()
        return VideoMetadata(**data)

    async def list_videos(
        self,
        status: VideoStatus | None = None,
        has_ip_match: bool | None = None,
        channel_id: str | None = None,
        sort_by: str = "discovered_at",
        sort_desc: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[VideoMetadata], int]:
        """
        List videos with filters and pagination.

        Args:
            status: Filter by video status
            has_ip_match: Filter by IP match presence
            channel_id: Filter by channel ID
            sort_by: Field to sort by
            sort_desc: Sort descending
            limit: Maximum results
            offset: Skip first N results

        Returns:
            Tuple of (videos list, total count)
        """
        query = self.videos_collection

        # Apply filters
        if status:
            query = query.where("status", "==", status.value)
        if has_ip_match is not None:
            # Filter by matched_ips array not empty
            if has_ip_match:
                query = query.where("matched_ips", "!=", [])
        if channel_id:
            query = query.where("channel_id", "==", channel_id)

        # Sort
        direction = firestore.Query.DESCENDING if sort_desc else firestore.Query.ASCENDING
        query = query.order_by(sort_by, direction=direction)

        # Get total count (for pagination)
        # Note: In production, consider caching this or using count aggregations
        total_docs = query.stream()
        total = sum(1 for _ in total_docs)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        docs = query.stream()
        videos = []
        for doc in docs:
            data = doc.to_dict()
            videos.append(VideoMetadata(**data))

        return videos, total

    async def get_channel(self, channel_id: str) -> ChannelProfile | None:
        """Get a single channel by ID."""
        doc = self.channels_collection.document(channel_id).get()
        if not doc.exists:
            return None

        data = doc.to_dict()
        return ChannelProfile(**data)

    async def list_channels(
        self,
        min_risk: int | None = None,
        tier: ChannelTier | None = None,
        sort_by: str = "risk_score",
        sort_desc: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ChannelProfile], int]:
        """
        List channels with filters and pagination.

        Args:
            min_risk: Minimum risk score filter
            tier: Filter by tier
            sort_by: Field to sort by
            sort_desc: Sort descending
            limit: Maximum results
            offset: Skip first N results

        Returns:
            Tuple of (channels list, total count)
        """
        query = self.channels_collection

        # Apply filters
        if min_risk is not None:
            query = query.where("risk_score", ">=", min_risk)
        if tier:
            query = query.where("tier", "==", tier.value)

        # Sort
        direction = firestore.Query.DESCENDING if sort_desc else firestore.Query.ASCENDING
        query = query.order_by(sort_by, direction=direction)

        # Get total count
        total_docs = query.stream()
        total = sum(1 for _ in total_docs)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        docs = query.stream()
        channels = []
        for doc in docs:
            data = doc.to_dict()
            channels.append(ChannelProfile(**data))

        return channels, total

    async def get_channel_stats(self) -> ChannelStats:
        """Get channel tier distribution statistics."""
        stats = ChannelStats()

        # Load all channels and count by tier in memory
        # (tier field may not be stored in Firestore, computed from risk_score)
        all_channels = self.channels_collection.stream()

        for doc in all_channels:
            data = doc.to_dict()
            channel = ChannelProfile(**data)

            # Count by tier
            if channel.tier == ChannelTier.CRITICAL:
                stats.critical += 1
            elif channel.tier == ChannelTier.HIGH:
                stats.high += 1
            elif channel.tier == ChannelTier.MEDIUM:
                stats.medium += 1
            elif channel.tier == ChannelTier.LOW:
                stats.low += 1
            elif channel.tier == ChannelTier.MINIMAL:
                stats.minimal += 1

        stats.total = stats.critical + stats.high + stats.medium + stats.low + stats.minimal
        return stats

    async def get_last_discovery_run(self) -> dict | None:
        """Get the most recent discovery run metrics."""
        try:
            # Query discovery_metrics collection for most recent run
            metrics_docs = (
                self.db.collection("discovery_metrics")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream()
            )

            for doc in metrics_docs:
                data = doc.to_dict()
                return {
                    "timestamp": data.get("timestamp"),
                    "videos_discovered": data.get("videos_discovered", 0),
                    "quota_used": data.get("quota_used", 0),
                    "channels_tracked": data.get("channels_tracked", 0),
                    "duration_seconds": data.get("duration_seconds", 0.0),
                    "tier_breakdown": data.get("tier_breakdown", {}),
                }

            return None
        except Exception:
            # If collection doesn't exist or query fails, return None
            return None

    async def get_24h_summary(self) -> dict:
        """Get 24-hour activity summary."""
        now = datetime.now()
        yesterday = now - timedelta(hours=24)

        # Count videos discovered in last 24h
        videos_discovered = len(
            list(self.videos_collection.where("discovered_at", ">=", yesterday).stream())
        )

        # Count unique channels
        channels_tracked = len(list(self.channels_collection.stream()))

        # Get today's quota usage from quota_usage collection
        today_key = now.strftime("%Y-%m-%d")
        quota_doc = self.db.collection("quota_usage").document(today_key).get()
        quota_used = 0
        if quota_doc.exists:
            quota_data = quota_doc.to_dict()
            quota_used = quota_data.get("units_used", 0)

        # Get last discovery run stats
        last_run = await self.get_last_discovery_run()

        # Note: videos_analyzed, infringements_found
        # should be queried from BigQuery when vision-analyzer is implemented
        return {
            "videos_discovered": videos_discovered,
            "channels_tracked": channels_tracked,
            "quota_used": quota_used,
            "quota_total": 10000,
            "videos_analyzed": 0,  # TODO: Query from BigQuery results
            "infringements_found": 0,  # TODO: Query from BigQuery results
            "period_start": yesterday,
            "period_end": now,
            "last_run": last_run,
        }


firestore_client = FirestoreClient()
