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

        # Map analysis field to vision_analysis for API response
        if data.get("analysis"):
            data["vision_analysis"] = data["analysis"]

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

        # OPTIMIZED: Apply limit in Firestore query to reduce data transfer
        # Fetch slightly more than needed to account for deleted videos
        fetch_limit = (offset + limit) * 2  # 2x buffer for deleted videos
        query = query.limit(fetch_limit)

        # Execute query with limit
        all_docs = list(query.stream())

        # Filter out deleted videos
        non_deleted_docs = [doc for doc in all_docs if not doc.to_dict().get("deleted", False)]

        # Apply pagination in Python (after filtering deleted)
        paginated_docs = non_deleted_docs[offset:offset + limit]

        # Get accurate total from system_stats
        try:
            stats_doc = self.db.collection("system_stats").document("global").get()
            if stats_doc.exists:
                total = stats_doc.to_dict().get("total_videos", len(non_deleted_docs))
            else:
                total = len(non_deleted_docs)
        except Exception:
            total = len(non_deleted_docs)

        # Convert to VideoMetadata
        videos = []
        for doc in paginated_docs:
            data = doc.to_dict()

            # Map analysis field to vision_analysis for API response
            if data.get("analysis"):
                data["vision_analysis"] = data["analysis"]

            videos.append(VideoMetadata(**data))

        return videos, total

    def _get_channel_stats_for_ids(self, channel_ids: list[str]) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
        """Calculate video counts, views, infringements, and cleared for SPECIFIC channels only."""
        channel_counts = {}
        channel_views = {}
        channel_infringements = {}
        channel_cleared = {}

        # Query videos ONLY for the specified channels (using 'in' operator)
        # Firestore 'in' has a limit of 10, so batch if needed
        batch_size = 10
        for i in range(0, len(channel_ids), batch_size):
            batch = channel_ids[i:i + batch_size]

            videos = self.videos_collection.where("channel_id", "in", batch).stream()

            for video in videos:
                data = video.to_dict()
                channel_id = data.get("channel_id")
                if channel_id:
                    # Count videos
                    channel_counts[channel_id] = channel_counts.get(channel_id, 0) + 1

                    # Sum views
                    view_count = data.get("view_count", 0)
                    if view_count:
                        channel_views[channel_id] = channel_views.get(channel_id, 0) + view_count

                    # Count infringements and cleared (from actual analysis results)
                    status = data.get("status")
                    if status == "analyzed":
                        analysis = data.get("analysis")
                        if analysis and isinstance(analysis, dict):
                            contains_infringement = analysis.get("contains_infringement", False)
                            if contains_infringement:
                                channel_infringements[channel_id] = channel_infringements.get(channel_id, 0) + 1
                            else:
                                channel_cleared[channel_id] = channel_cleared.get(channel_id, 0) + 1

        return channel_counts, channel_views, channel_infringements, channel_cleared

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
        action_status: str | None = None,
        sort_by: str = "last_seen_at",
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
        import logging
        logger = logging.getLogger(__name__)
        from datetime import datetime, timezone

        # Step 1: Get total count from system_stats
        try:
            stats_doc = self.db.collection("system_stats").document("global").get()
            total_channels = stats_doc.to_dict().get("total_channels", 0) if stats_doc.exists else 0
        except Exception:
            total_channels = 0

        # Step 2: Build Firestore query with filters and sorting
        query = self.channels_collection

        # Apply filters at Firestore level (if supported)
        if tier:
            query = query.where("tier", "==", tier.value if hasattr(tier, 'value') else tier)

        # Apply sorting at Firestore level
        sort_direction = firestore.Query.DESCENDING if sort_desc else firestore.Query.ASCENDING

        # Map API sort fields to Firestore fields
        firestore_sort_fields = {
            "risk_score": "channel_risk",
            "total_videos_found": "total_videos_found",
            "confirmed_infringements": "confirmed_infringements",
            "last_scanned_at": "last_scanned_at",
            "last_seen_at": "last_seen_at",
        }

        firestore_sort_field = firestore_sort_fields.get(sort_by, "last_seen_at")
        query = query.order_by(firestore_sort_field, direction=sort_direction)

        # Apply pagination at Firestore level
        query = query.limit(limit).offset(offset)

        # Execute query
        channel_docs = list(query.stream())

        # Convert to ChannelProfile objects
        all_channels = []
        for doc in channel_docs:
            data = doc.to_dict()
            channel_id = data.get("channel_id", doc.id)

            # Use pre-aggregated stats from channel document
            # These are maintained by discovery-service when videos are discovered
            total_videos_found = data.get("total_videos_found", 0)
            total_views = data.get("total_views", 0)

            # For infringements/cleared, we still need to query videos since these change with analysis
            # TODO: Also pre-aggregate these in vision-analyzer-service
            confirmed_infringements = data.get("confirmed_infringements", 0)
            videos_cleared = data.get("videos_cleared", 0)

            # Fill in missing fields with defaults
            channel_data = {
                "channel_id": channel_id,
                "channel_title": data.get("channel_title", "Unknown"),
                "discovered_at": data.get("discovered_at", datetime.now(timezone.utc)),  # Required field!
                "total_videos_found": total_videos_found,  # Pre-aggregated
                "confirmed_infringements": confirmed_infringements,  # Pre-aggregated
                "videos_cleared": videos_cleared,  # Pre-aggregated
                "last_infringement_date": data.get("last_infringement_date"),
                "infringement_rate": data.get("infringement_rate", 0.0),
                "risk_score": data.get("channel_risk", 0),
                "tier": data.get("tier", "minimal").lower(),  # Enum expects lowercase!
                "is_newly_discovered": data.get("is_newly_discovered", True),
                "last_scanned_at": data.get("last_scanned_at"),
                "next_scan_at": data.get("next_scan_at"),
                "last_upload_date": data.get("last_seen_at"),  # Use last_seen_at as upload date
                "posting_frequency_days": data.get("posting_frequency_days"),
                "thumbnail_url": data.get("thumbnail_url"),
                "subscriber_count": data.get("subscriber_count"),
                "video_count": data.get("video_count"),
                "total_views": total_views,  # Sum of view_count from all discovered videos
                "action_status": data.get("action_status"),
                "assigned_to": data.get("assigned_to"),
                "notes": data.get("notes"),
                "last_action_date": data.get("last_action_date"),
            }
            try:
                all_channels.append(ChannelProfile(**channel_data))
            except Exception as e:
                logger.error(f"Failed to create ChannelProfile: {e}, data: {channel_data}")
                # Skip invalid channels
                continue

        # Filtering/sorting/pagination already done at Firestore level
        logger.info(f"Returning {len(all_channels)} channels (total in DB: {total_channels})")
        return all_channels, total_channels

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
        from datetime import timezone
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)

        # Count videos discovered in last 24h - USE AGGREGATION!
        from google.cloud.firestore_v1.aggregation import AggregationQuery

        try:
            query = self.videos_collection.where("discovered_at", ">=", yesterday)
            agg_query = AggregationQuery(query)
            agg_query.count(alias="total")
            result = agg_query.get()
            videos_discovered = result[0][0].value if result else 0
        except Exception:
            videos_discovered = 0

        # Get total channels from system_stats (faster than aggregation)
        try:
            stats_doc = self.db.collection("system_stats").document("global").get()
            if stats_doc.exists:
                channels_tracked = stats_doc.to_dict().get("total_channels", 0)
            else:
                # Fallback: count channels using aggregation
                query = self.channels_collection
                agg_query = AggregationQuery(query)
                agg_query.count(alias="total")
                result = agg_query.get()
                channels_tracked = result[0][0].value if result else 0
        except Exception as e:
            logger.warning(f"Failed to get channel count: {e}")
            channels_tracked = 0

        # Get today's quota usage from quota_usage collection
        today_key = now.strftime("%Y-%m-%d")
        quota_doc = self.db.collection("quota_usage").document(today_key).get()
        quota_used = 0
        if quota_doc.exists:
            quota_data = quota_doc.to_dict()
            quota_used = quota_data.get("units_used", 0)

        # Get last discovery run stats
        last_run = await self.get_last_discovery_run()

        # Count videos analyzed (use system_stats for fast O(1) lookup)
        videos_analyzed = 0
        infringements_found = 0

        # Get stats from system_stats document (O(1) - much faster than querying!)
        stats_doc = self.db.collection("system_stats").document("global").get()
        if stats_doc.exists:
            stats_data = stats_doc.to_dict()
            # Get total analyzed from aggregated stats (updated by vision-analyzer)
            videos_analyzed = stats_data.get("total_analyzed", 0)
            infringements_found = stats_data.get("total_infringements", 0)

        return {
            "videos_discovered": videos_discovered,
            "channels_tracked": channels_tracked,
            "quota_used": quota_used,
            "quota_total": 10000,
            "videos_analyzed": videos_analyzed,
            "infringements_found": infringements_found,
            "period_start": yesterday,
            "period_end": now,
            "last_run": last_run,
        }


firestore_client = FirestoreClient()


def get_firestore_client() -> FirestoreClient:
    """Dependency injection for FastAPI."""
    return firestore_client
