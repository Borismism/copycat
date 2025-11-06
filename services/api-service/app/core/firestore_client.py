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

        # Execute query and filter deleted videos in Python (since Firestore doesn't support "is null OR false")
        all_docs = list(query.stream())

        # Filter out deleted videos
        non_deleted_docs = [doc for doc in all_docs if not doc.to_dict().get("deleted", False)]
        total = len(non_deleted_docs)

        # Apply pagination in Python
        paginated_docs = non_deleted_docs[offset:offset + limit]

        # Convert to VideoMetadata
        videos = []
        for doc in paginated_docs:
            data = doc.to_dict()

            # Map analysis field to vision_analysis for API response
            if data.get("analysis"):
                data["vision_analysis"] = data["analysis"]

            videos.append(VideoMetadata(**data))

        return videos, total

    def _get_all_channel_stats(self) -> tuple[dict[str, int], dict[str, int]]:
        """Calculate video counts and total views for ALL channels in one query."""
        all_videos = self.videos_collection.stream()
        channel_counts = {}
        channel_views = {}

        for video in all_videos:
            data = video.to_dict()
            channel_id = data.get("channel_id")
            if channel_id:
                # Count videos
                channel_counts[channel_id] = channel_counts.get(channel_id, 0) + 1
                # Sum views
                view_count = data.get("view_count", 0)
                if view_count:
                    channel_views[channel_id] = channel_views.get(channel_id, 0) + view_count

        return channel_counts, channel_views

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
        # Get ALL channels and sort in memory (Firestore emulator has issues with orderBy)
        all_channels_docs = list(self.channels_collection.stream())
        total = len(all_channels_docs)

        # Process ALL channels first
        import logging
        logger = logging.getLogger(__name__)
        from datetime import datetime, timezone

        # Get video counts and view counts for ALL channels in one query
        channel_video_counts, channel_views_map = self._get_all_channel_stats()

        all_channels = []
        for doc in all_channels_docs:
            data = doc.to_dict()
            channel_id = data.get("channel_id", doc.id)

            # Get total views and actual video count from the pre-computed maps
            total_views = channel_views_map.get(channel_id, 0)
            actual_video_count = channel_video_counts.get(channel_id, 0)

            # Fill in missing fields with defaults
            channel_data = {
                "channel_id": channel_id,
                "channel_title": data.get("channel_title", "Unknown"),
                "discovered_at": data.get("discovered_at", datetime.now(timezone.utc)),  # Required field!
                "total_videos_found": actual_video_count,  # Use actual count from videos collection
                "confirmed_infringements": data.get("confirmed_infringements", data.get("infringing_videos_count", 0)),
                "videos_cleared": data.get("videos_cleared", 0),
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

        # Apply filters
        filtered_channels = all_channels
        if min_risk is not None:
            filtered_channels = [ch for ch in filtered_channels if ch.risk_score >= min_risk]
        if tier:
            filtered_channels = [ch for ch in filtered_channels if ch.tier == tier]
        if action_status:
            filtered_channels = [ch for ch in filtered_channels if ch.action_status == action_status]

        # Update total to reflect filtered count
        filtered_total = len(filtered_channels)

        # Sort in memory
        sort_key_map = {
            "video_count": lambda ch: ch.total_videos_found,
            "total_videos_found": lambda ch: ch.total_videos_found,
            "risk_score": lambda ch: ch.risk_score,
            "confirmed_infringements": lambda ch: ch.confirmed_infringements or 0,
            "last_scanned_at": lambda ch: ch.last_scanned_at or datetime.min.replace(tzinfo=timezone.utc),
            "discovered_at": lambda ch: ch.discovered_at,
            "last_seen_at": lambda ch: ch.last_upload_date or datetime.min.replace(tzinfo=timezone.utc),
        }

        sort_key_func = sort_key_map.get(sort_by, lambda ch: ch.total_videos_found)
        filtered_channels.sort(key=sort_key_func, reverse=sort_desc)

        # Apply pagination
        paginated_channels = filtered_channels[offset:offset+limit]

        logger.info(f"Returning {len(paginated_channels)} channels out of {filtered_total} filtered (total in DB: {total})")
        return paginated_channels, filtered_total

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

        # Count videos analyzed in last 24h (status = "analyzed")
        videos_analyzed = 0
        infringements_found = 0

        try:
            analyzed_videos = self.videos_collection.where("status", "==", "analyzed").stream()

            for video_doc in analyzed_videos:
                video_data = video_doc.to_dict()

                # Check if analyzed in last 24h
                last_analyzed = video_data.get("last_analyzed_at") or video_data.get("updated_at")
                if last_analyzed:
                    # Handle both datetime and string timestamps
                    if isinstance(last_analyzed, str):
                        from dateutil import parser
                        last_analyzed = parser.isoparse(last_analyzed)

                    # Ensure timezone-aware comparison
                    if last_analyzed.tzinfo is None:
                        last_analyzed = last_analyzed.replace(tzinfo=timezone.utc)

                    if last_analyzed >= yesterday:
                        videos_analyzed += 1

                        # Check for infringement (from analysis field with multi-IP format)
                        analysis = video_data.get("analysis", {})
                        if isinstance(analysis, dict) and analysis.get("ip_results"):
                            # Multi-IP format: check if any IP has infringement
                            for ip_result in analysis.get("ip_results", []):
                                if ip_result.get("contains_infringement"):
                                    infringements_found += 1
                                    break
        except Exception:
            # If query fails, return 0 (vision analyzer may not be deployed yet)
            pass

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
