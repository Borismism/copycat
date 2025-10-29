"""Smart risk-based channel tracking."""

import logging
from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from ..models import ChannelProfile

logger = logging.getLogger(__name__)


class ChannelTracker:
    """
    Smart channel tracking with risk-based scanning.

    Risk factors:
    - Volume: More videos found = higher risk
    - Confirmed infringements: Gemini confirmed = MAX risk
    - Activity: Recent uploads = higher risk

    Scan frequency based on risk:
    - 80-100: Every 6 hours (CRITICAL - confirmed infringers)
    - 60-79: Daily (HIGH - lots of matching content)
    - 40-59: Every 3 days (MEDIUM)
    - 20-39: Weekly (LOW)
    - 0-19: Monthly (MINIMAL)
    """

    # Scan frequency mapping (hours) based on risk score
    SCAN_FREQUENCY_HOURS = {
        "critical": 6,   # 80-100: Every 6 hours
        "high": 24,      # 60-79: Daily
        "medium": 72,    # 40-59: Every 3 days
        "low": 168,      # 20-39: Weekly
        "minimal": 720,  # 0-19: Monthly
    }

    def __init__(self, firestore_client: firestore.Client, channels_collection: str = "channels"):
        """Initialize channel tracker."""
        self.firestore = firestore_client
        self.channels_collection = channels_collection
        logger.info("ChannelTracker initialized with risk-based scoring")

    def get_or_create_profile(
        self, channel_id: str, channel_title: str
    ) -> ChannelProfile:
        """
        Get existing channel profile or create new one.

        Args:
            channel_id: YouTube channel ID
            channel_title: Channel name

        Returns:
            ChannelProfile
        """
        doc_ref = self.firestore.collection(self.channels_collection).document(
            channel_id
        )

        try:
            doc = doc_ref.get()

            if doc.exists:
                # Return existing profile
                data = doc.to_dict()
                profile = ChannelProfile(**data)
                logger.debug(f"Loaded channel {channel_id}")
                return profile
            else:
                # Create new profile with initial risk
                now = datetime.now(timezone.utc)
                profile = ChannelProfile(
                    channel_id=channel_id,
                    channel_title=channel_title,
                    total_videos_found=0,
                    confirmed_infringements=0,
                    risk_score=0,  # Will be calculated when videos are added
                    last_scanned_at=now,
                    next_scan_at=now,  # Scan immediately
                    last_upload_date=None,
                    posting_frequency_days=7.0,
                    discovered_at=now,
                )

                doc_ref.set(profile.model_dump())
                logger.info(f"Created channel profile: {channel_id}")
                return profile

        except Exception as e:
            logger.error(f"Error with channel {channel_id}: {e}")
            raise

    def calculate_risk_score(self, profile: ChannelProfile) -> int:
        """
        Calculate intelligent risk score (0-100) for a channel.

        NEW SMART LOGIC:
        - All videos cleared (no infringement) → 5-15 (MINIMAL)
        - ANY confirmed infringement → Critical, unless old
        - Time decay: Old infringements (>90 days) reduce risk
        - Infringement rate is key metric

        Risk tiers:
        - 0-19: MINIMAL - Clean channel or all cleared
        - 20-39: LOW - Low infringement rate, old violations
        - 40-59: MEDIUM - Moderate infringement rate
        - 60-79: HIGH - High infringement rate or recent violation
        - 80-100: CRITICAL - Active infringer with recent violations

        Args:
            profile: Channel profile to evaluate

        Returns:
            Risk score 0-100
        """
        risk = 0
        now = datetime.now(timezone.utc)

        # NEWLY DISCOVERED: Start at MEDIUM risk (50) until evaluated
        if profile.is_newly_discovered:
            # Give benefit of doubt, but prioritize evaluation
            if profile.total_videos_found >= 10:
                return 55  # Slightly higher - lots of content to check
            elif profile.total_videos_found >= 5:
                return 50  # Medium priority
            else:
                return 45  # Lower priority - not much content

        # EVALUATED CHANNELS: Calculate based on actual behavior

        total_reviewed = profile.confirmed_infringements + profile.videos_cleared

        # Special Case 1: ALL VIDEOS CLEARED (No infringement found)
        if total_reviewed > 0 and profile.confirmed_infringements == 0:
            # Clean channel! Very low risk
            if profile.videos_cleared >= 10:
                return 5  # Very clean - many videos checked
            elif profile.videos_cleared >= 5:
                return 10  # Clean channel
            else:
                return 15  # Probably clean, needs more evaluation

        # Special Case 2: NO VIDEOS REVIEWED YET
        if total_reviewed == 0:
            # Not evaluated yet, use volume as proxy
            if profile.total_videos_found >= 10:
                return 40  # Lots of unreviewed content
            elif profile.total_videos_found >= 5:
                return 35
            else:
                return 30

        # INFRINGEMENT ANALYSIS: Channel has confirmed violations

        # Calculate infringement rate
        infringement_rate = profile.confirmed_infringements / total_reviewed if total_reviewed > 0 else 0

        # Base risk from infringement rate
        if infringement_rate >= 0.75:  # 75%+ infringement
            risk = 90
        elif infringement_rate >= 0.50:  # 50-74% infringement
            risk = 70
        elif infringement_rate >= 0.25:  # 25-49% infringement
            risk = 50
        elif infringement_rate > 0:  # 1-24% infringement
            risk = 35

        # Time decay: Reduce risk if last infringement was long ago
        if profile.last_infringement_date:
            days_since_last_infringement = (now - profile.last_infringement_date).days

            if days_since_last_infringement > 180:  # 6+ months clean
                risk = int(risk * 0.4)  # 60% reduction
            elif days_since_last_infringement > 90:  # 3-6 months clean
                risk = int(risk * 0.6)  # 40% reduction
            elif days_since_last_infringement > 30:  # 1-3 months clean
                risk = int(risk * 0.8)  # 20% reduction
            # If < 30 days: no reduction (recent infringer)

        # Boost risk if currently active uploader with infringements
        if profile.last_upload_date and profile.confirmed_infringements > 0:
            days_since_upload = (now - profile.last_upload_date).days

            if days_since_upload <= 7:  # Uploaded in last week
                risk += 20
            elif days_since_upload <= 30:  # Uploaded in last month
                risk += 10
            elif days_since_upload <= 90:  # Uploaded in last 3 months
                risk += 5

        # Volume multiplier for spam channels
        if profile.confirmed_infringements >= 10:
            risk += 10  # Prolific infringer
        elif profile.confirmed_infringements >= 5:
            risk += 5

        # Ensure minimum risk for any channel with infringements
        if profile.confirmed_infringements > 0:
            risk = max(risk, 25)  # At least LOW tier

        return min(risk, 100)

    def calculate_next_scan_time(self, risk_score: int) -> datetime:
        """
        Calculate next scan time based on risk score.

        Risk-based scheduling:
        - 80-100: Every 6 hours (CRITICAL)
        - 60-79: Daily (HIGH)
        - 40-59: Every 3 days (MEDIUM)
        - 20-39: Weekly (LOW)
        - 0-19: Monthly (MINIMAL)

        Args:
            risk_score: Risk score 0-100

        Returns:
            Next scan datetime
        """
        now = datetime.now(timezone.utc)

        if risk_score >= 80:
            hours = 6  # Critical - scan every 6 hours
        elif risk_score >= 60:
            hours = 24  # High - daily
        elif risk_score >= 40:
            hours = 72  # Medium - every 3 days
        elif risk_score >= 20:
            hours = 168  # Low - weekly
        else:
            hours = 720  # Minimal - monthly

        return now + timedelta(hours=hours)

    def update_after_scan(
        self,
        channel_id: str,
        found_videos: bool,
        latest_upload_date: datetime | None = None
    ) -> ChannelProfile:
        """
        Update channel profile after scanning.

        Args:
            channel_id: Channel ID
            found_videos: Whether we found new matching videos
            latest_upload_date: Most recent upload date from scanned videos

        Returns:
            Updated profile
        """
        doc_ref = self.firestore.collection(self.channels_collection).document(
            channel_id
        )

        try:
            doc = doc_ref.get()

            if not doc.exists:
                raise ValueError(f"Channel {channel_id} does not exist")

            data = doc.to_dict()
            profile = ChannelProfile(**data)

            now = datetime.now(timezone.utc)
            profile.last_scanned_at = now
            profile.is_newly_discovered = False

            if latest_upload_date:
                if profile.last_upload_date is None or latest_upload_date > profile.last_upload_date:
                    profile.last_upload_date = latest_upload_date

            profile.risk_score = self.calculate_risk_score(profile)
            profile.next_scan_at = self.calculate_next_scan_time(profile.risk_score)

            doc_ref.set(profile.model_dump())

            logger.info(
                f"Updated channel {channel_id}: risk={profile.risk_score}, "
                f"last_upload={profile.last_upload_date}, "
                f"next_scan={profile.next_scan_at.strftime('%Y-%m-%d %H:%M')}"
            )

            return profile

        except Exception as e:
            logger.error(f"Error updating channel {channel_id}: {e}")
            raise

    def increment_video_count(
        self, channel_id: str, video_published_at: datetime | None = None
    ) -> None:
        """
        Increment total videos found for a channel and track upload date.

        Called when we discover a new video from this channel.

        Args:
            channel_id: Channel ID
            video_published_at: When this video was published (optional)
        """
        doc_ref = self.firestore.collection(self.channels_collection).document(
            channel_id
        )

        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                profile = ChannelProfile(**data)

                profile.total_videos_found += 1

                if video_published_at:
                    if profile.last_upload_date is None or video_published_at > profile.last_upload_date:
                        profile.last_upload_date = video_published_at

                profile.risk_score = self.calculate_risk_score(profile)
                profile.next_scan_at = self.calculate_next_scan_time(profile.risk_score)

                doc_ref.set(profile.model_dump())

                logger.debug(
                    f"Channel {channel_id}: {profile.total_videos_found} videos, "
                    f"risk={profile.risk_score}, last_upload={profile.last_upload_date}"
                )

        except Exception as e:
            logger.error(f"Error incrementing video count for {channel_id}: {e}")

    def mark_video_as_infringement(
        self, channel_id: str, infringement_date: datetime | None = None
    ) -> None:
        """
        Mark a video from this channel as confirmed infringement.

        Called when Gemini analysis confirms a video is infringing.

        Args:
            channel_id: Channel ID
            infringement_date: When the infringing video was published
        """
        doc_ref = self.firestore.collection(self.channels_collection).document(
            channel_id
        )

        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                profile = ChannelProfile(**data)

                profile.confirmed_infringements += 1

                # Track most recent infringement
                if infringement_date:
                    if profile.last_infringement_date is None or infringement_date > profile.last_infringement_date:
                        profile.last_infringement_date = infringement_date

                profile.risk_score = self.calculate_risk_score(profile)
                profile.next_scan_at = self.calculate_next_scan_time(profile.risk_score)

                doc_ref.set(profile.model_dump())

                logger.info(
                    f"Channel {channel_id}: Infringement confirmed! "
                    f"Total: {profile.confirmed_infringements}, Risk: {profile.risk_score}"
                )

        except Exception as e:
            logger.error(f"Error marking infringement for {channel_id}: {e}")

    def mark_video_as_cleared(self, channel_id: str) -> None:
        """
        Mark a video from this channel as NOT infringing (false positive).

        Called when Gemini analysis confirms a video is clean/fair use.

        Args:
            channel_id: Channel ID
        """
        doc_ref = self.firestore.collection(self.channels_collection).document(
            channel_id
        )

        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                profile = ChannelProfile(**data)

                profile.videos_cleared += 1

                profile.risk_score = self.calculate_risk_score(profile)
                profile.next_scan_at = self.calculate_next_scan_time(profile.risk_score)

                doc_ref.set(profile.model_dump())

                logger.info(
                    f"Channel {channel_id}: Video cleared. "
                    f"Total cleared: {profile.videos_cleared}, Risk: {profile.risk_score}"
                )

        except Exception as e:
            logger.error(f"Error marking video cleared for {channel_id}: {e}")

    def get_channels_due_for_scan(self, limit: int = 100) -> list[ChannelProfile]:
        """
        Get channels that need scanning now, ordered by risk score.

        Args:
            limit: Maximum channels to return

        Returns:
            List of channels due for scan, highest risk first
        """
        try:
            now = datetime.now(timezone.utc)

            # Query channels due for scan
            query = (
                self.firestore.collection(self.channels_collection)
                .where("next_scan_at", "<=", now)
                .order_by("next_scan_at")
                .limit(limit * 2)  # Get extra to sort by risk
            )

            docs = query.stream()

            channels = []
            for doc in docs:
                try:
                    profile = ChannelProfile(**doc.to_dict())
                    channels.append(profile)
                except Exception as e:
                    logger.error(f"Error parsing channel {doc.id}: {e}")
                    continue

            # Sort by risk score descending (highest risk first)
            channels.sort(key=lambda c: c.risk_score, reverse=True)

            logger.info(
                f"Found {len(channels[:limit])} channels due for scan "
                f"(avg risk: {sum(c.risk_score for c in channels[:limit]) / len(channels[:limit]):.1f})"
                if channels else "Found 0 channels due for scan"
            )

            return channels[:limit]

        except Exception as e:
            logger.error(f"Error querying channels: {e}")
            return []

    def get_all_channels(
        self, min_risk: int | None = None, limit: int = 100
    ) -> list[ChannelProfile]:
        """
        Get all tracked channels, optionally filtered by minimum risk score.

        Args:
            min_risk: Minimum risk score (optional)
            limit: Maximum channels to return

        Returns:
            List of channels, highest risk first
        """
        try:
            query = self.firestore.collection(self.channels_collection)

            # Filter by risk if specified
            if min_risk is not None:
                query = query.where("risk_score", ">=", min_risk)

            # Order by risk descending
            query = query.order_by("risk_score", direction="DESCENDING").limit(limit)

            docs = query.stream()

            channels = []
            for doc in docs:
                try:
                    profile = ChannelProfile(**doc.to_dict())
                    channels.append(profile)
                except Exception as e:
                    logger.error(f"Error parsing channel {doc.id}: {e}")
                    continue

            logger.info(f"Retrieved {len(channels)} channels")
            return channels

        except Exception as e:
            logger.error(f"Error retrieving channels: {e}")
            return []

    def mark_deep_scan_complete(self, channel_id: str) -> None:
        """
        Mark that deep scan has been completed for this channel.

        Args:
            channel_id: Channel ID
        """
        doc_ref = self.firestore.collection(self.channels_collection).document(
            channel_id
        )

        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                profile = ChannelProfile(**data)

                now = datetime.now(timezone.utc)
                profile.deep_scan_completed = True
                profile.deep_scan_at = now

                doc_ref.set(profile.model_dump())

                logger.info(f"Channel {channel_id}: Deep scan marked complete")

        except Exception as e:
            logger.error(f"Error marking deep scan complete for {channel_id}: {e}")

    def get_channels_needing_deep_scan(self, limit: int = 50) -> list[ChannelProfile]:
        """
        Get channels that haven't had a deep scan yet.

        Returns channels where deep_scan_completed = False, prioritized by:
        1. Newly discovered channels (is_newly_discovered = True)
        2. Risk score (highest first)
        3. Excludes channels scanned in last hour (avoid duplicates)

        Args:
            limit: Maximum channels to return

        Returns:
            List of channels needing deep scan
        """
        try:
            # Get channels without deep scan OR last scanned > 1 hour ago
            # This prevents re-scanning same channels in rapid succession
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

            # Query channels without deep scan
            query = (
                self.firestore.collection(self.channels_collection)
                .where("deep_scan_completed", "==", False)
                .limit(limit * 3)  # Get extra for filtering and sorting
            )

            docs = query.stream()

            channels = []
            for doc in docs:
                try:
                    profile = ChannelProfile(**doc.to_dict())

                    # Skip channels scanned in last hour (avoid duplicates in rapid runs)
                    if profile.last_scanned_at and profile.last_scanned_at > one_hour_ago:
                        continue

                    channels.append(profile)
                except Exception as e:
                    logger.error(f"Error parsing channel {doc.id}: {e}")
                    continue

            # Sort by: newly discovered first, then by risk score
            channels.sort(key=lambda c: (not c.is_newly_discovered, -c.risk_score))

            logger.info(
                f"Found {len(channels[:limit])} channels needing deep scan "
                f"(filtered out recently scanned)"
            )

            return channels[:limit]

        except Exception as e:
            logger.error(f"Error querying channels needing deep scan: {e}")
            return []

    def get_statistics(self) -> dict:
        """Get channel tracking statistics."""
        try:
            docs = self.firestore.collection(self.channels_collection).stream()

            stats = {
                "total_channels": 0,
                "by_risk_level": {
                    "critical": 0,  # 80-100
                    "high": 0,       # 60-79
                    "medium": 0,     # 40-59
                    "low": 0,        # 20-39
                    "minimal": 0,    # 0-19
                },
                "total_videos": 0,
                "confirmed_infringements": 0,
                "avg_risk_score": 0.0,
                "deep_scan_completed": 0,
                "deep_scan_pending": 0,
            }

            total_risk = 0
            count = 0

            for doc in docs:
                try:
                    profile = ChannelProfile(**doc.to_dict())

                    stats["total_channels"] += 1
                    stats["total_videos"] += profile.total_videos_found
                    stats["confirmed_infringements"] += profile.confirmed_infringements

                    if profile.deep_scan_completed:
                        stats["deep_scan_completed"] += 1
                    else:
                        stats["deep_scan_pending"] += 1

                    # Categorize by risk
                    if profile.risk_score >= 80:
                        stats["by_risk_level"]["critical"] += 1
                    elif profile.risk_score >= 60:
                        stats["by_risk_level"]["high"] += 1
                    elif profile.risk_score >= 40:
                        stats["by_risk_level"]["medium"] += 1
                    elif profile.risk_score >= 20:
                        stats["by_risk_level"]["low"] += 1
                    else:
                        stats["by_risk_level"]["minimal"] += 1

                    total_risk += profile.risk_score
                    count += 1

                except Exception as e:
                    logger.error(f"Error in statistics: {e}")
                    continue

            if count > 0:
                stats["avg_risk_score"] = total_risk / count

            return stats

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {"error": str(e)}
