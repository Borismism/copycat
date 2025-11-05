"""
Video Risk Calculator - 7-Factor Scoring (0-100)

Calculates video-level risk based on content characteristics and engagement.
This score represents 60% of the final scan priority.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class VideoRiskCalculator:
    """
    Calculate video risk score (0-100) based on 7 factors.

    Factors:
    1. IP Character Match Quality (0-25 pts) - Relevance
    2. View Count (0-20 pts) - Impact
    3. View Velocity (0-20 pts) - Viral detection
    4. Age vs Views (0-15 pts) - Survivor bias
    5. Engagement Rate (0-10 pts) - Interaction
    6. Video Duration (0-5 pts) - Content type
    7. Scan History (0-5 pts) - Freshness
    """

    def calculate_video_risk(self, video: dict) -> dict:
        """
        Calculate comprehensive video risk score.

        Args:
            video: Video document from Firestore

        Returns:
            {
                "video_risk": int (0-100),
                "factors": {
                    "ip_match_quality": int,
                    "view_count": int,
                    "view_velocity": int,
                    "age_vs_views": int,
                    "engagement": int,
                    "duration": int,
                    "scan_history": int
                }
            }
        """
        video_id = video.get("video_id", "unknown")

        factors = {
            "ip_match_quality": self._calculate_ip_match_score(video),
            "view_count": self._calculate_view_count_score(video),
            "view_velocity": self._calculate_view_velocity_score(video),
            "age_vs_views": self._calculate_age_vs_views_score(video),
            "engagement": self._calculate_engagement_score(video),
            "duration": self._calculate_duration_score(video),
            "scan_history": self._calculate_scan_history_score(video),
        }

        # Sum all factors (max 100)
        video_risk = sum(factors.values())
        video_risk = max(0, min(100, video_risk))

        logger.info(
            f"Video {video_id}: risk={video_risk}, factors={factors}"
        )

        return {
            "video_risk": video_risk,
            "factors": factors,
        }

    def _calculate_ip_match_score(self, video: dict) -> int:
        """
        Factor 1: IP character match quality (0-25 points).

        Strong keyword matches = likely infringement.

        Scoring:
        - 0 matches: 0 pts
        - 1 exact match: 15 pts
        - 2+ exact matches: 20 pts
        - High priority IP (Superman, Batman, etc): +5 pts
        - AI generation keywords in title/desc: +5 pts
        """
        matched_ips = video.get("matched_ips", [])
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()

        if len(matched_ips) == 0:
            base = 0
        elif len(matched_ips) == 1:
            base = 15
        else:
            base = 20

        # High priority characters bonus
        high_priority_chars = ["superman", "batman", "wonder woman", "justice league"]
        has_high_priority = any(
            char.lower() in str(matched_ips).lower()
            for char in high_priority_chars
        )
        priority_bonus = 5 if has_high_priority else 0

        # AI generation keywords
        ai_keywords = [
            "ai generated", "sora", "runway", "kling", "pika",
            "ai movie", "ai video", "luma", "minimax"
        ]
        has_ai_keyword = any(kw in title or kw in description for kw in ai_keywords)
        ai_bonus = 5 if has_ai_keyword else 0

        return min(25, base + priority_bonus + ai_bonus)

    def _calculate_view_count_score(self, video: dict) -> int:
        """
        Factor 2: View count (0-20 points).

        More views = more damage if infringing.

        Scoring:
        - 0-1k views: 2 pts
        - 1k-10k: 5 pts
        - 10k-100k: 10 pts
        - 100k-1M: 15 pts
        - 1M-10M: 18 pts
        - 10M+: 20 pts (VIRAL - maximum priority!)
        """
        views = video.get("view_count", 0)

        if views < 1_000:
            return 2
        elif views < 10_000:
            return 5
        elif views < 100_000:
            return 10
        elif views < 1_000_000:
            return 15
        elif views < 10_000_000:
            return 18
        else:
            return 20

    def _calculate_view_velocity_score(self, video: dict) -> int:
        """
        Factor 3: View velocity (0-20 points).

        Going viral RIGHT NOW = scan IMMEDIATELY.

        Scoring:
        - >10k views/hour: 20 pts (MEGA VIRAL!)
        - >1k views/hour: 15 pts (very viral)
        - >100 views/hour: 10 pts (viral)
        - >10 views/hour: 5 pts (trending)
        - <10 views/hour: 0 pts (normal)
        """
        velocity = video.get("view_velocity", 0)

        if velocity > 10_000:
            return 20
        elif velocity > 1_000:
            return 15
        elif velocity > 100:
            return 10
        elif velocity > 10:
            return 5
        else:
            return 0

    def _calculate_age_vs_views_score(self, video: dict) -> int:
        """
        Factor 4: Age vs views (0-15 points).

        Old + high views = slipped through moderation = HIGH PRIORITY.

        Scoring:
        - >6 months + >100k views: 15 pts (SURVIVOR!)
        - >3 months + >50k views: 10 pts
        - >1 month + >10k views: 5 pts
        - Recent (<1 month): 0 pts (use view count only)
        - Old + low views: 0 pts (not urgent)
        """
        published_at = video.get("published_at")
        view_count = video.get("view_count", 0)

        if not published_at:
            return 0

        # Handle both datetime objects and timestamps
        if isinstance(published_at, datetime):
            pub_dt = published_at
        else:
            pub_dt = published_at

        age_days = (datetime.now(timezone.utc) - pub_dt).days

        # Recent videos: no survivor bonus
        if age_days <= 30:
            return 0

        # OLD + HIGH VIEWS = SURVIVOR
        if age_days > 180:  # >6 months
            if view_count > 100_000:
                return 15
            elif view_count > 10_000:
                return 5
            else:
                return 0
        elif age_days > 90:  # >3 months
            if view_count > 50_000:
                return 10
            elif view_count > 5_000:
                return 3
            else:
                return 0
        else:  # 1-3 months
            if view_count > 10_000:
                return 5
            else:
                return 0

    def _calculate_engagement_score(self, video: dict) -> int:
        """
        Factor 5: Engagement rate (0-10 points).

        High engagement = being watched/shared = higher impact.

        Scoring:
        - >5% engagement: 10 pts (highly engaging)
        - >2% engagement: 5 pts (engaging)
        - <2% engagement: 0 pts (normal)
        """
        views = video.get("view_count", 0)
        if views == 0:
            return 0

        likes = video.get("like_count", 0)
        comments = video.get("comment_count", 0)

        engagement_rate = (likes + comments) / views

        if engagement_rate > 0.05:
            return 10
        elif engagement_rate > 0.02:
            return 5
        else:
            return 0

    def _calculate_duration_score(self, video: dict) -> int:
        """
        Factor 6: Video duration (0-5 points).

        Longer videos = more substantial AI-generated content.

        Scoring:
        - >10 min: 5 pts (full movie - high priority)
        - 2-10 min: 3 pts (substantial clip)
        - 1-2 min: 1 pt (short clip)
        - <1 min: 0 pts (very short - likely shorts)
        """
        duration_seconds = video.get("duration_seconds", 0)

        if duration_seconds > 600:  # >10 min
            return 5
        elif duration_seconds > 120:  # 2-10 min
            return 3
        elif duration_seconds > 60:  # 1-2 min
            return 1
        else:
            return 0

    def _calculate_scan_history_score(self, video: dict) -> int:
        """
        Factor 7: Scan history (0-5 points).

        Never scanned = SUSPICIOUS, scanned clean many times = safe.

        Scoring:
        - Never scanned (NEW): 5 pts (INVESTIGATE!)
        - Scanned 1x, clean: 3 pts (still suspicious)
        - Scanned 2x, clean: 1 pt (probably fine)
        - Scanned 3+x, clean: 0 pts (confirmed clean)
        - Any scans with INFRINGEMENT: 5 pts (confirmed bad!)
        """
        scan_count = video.get("scan_count", 0)
        has_infringement = video.get("vision_analysis", {}).get("contains_infringement", False)

        # If infringement found, always max priority
        if has_infringement:
            return 5

        # Based on clean scan count
        if scan_count == 0:
            return 5  # NEW = SUSPICIOUS
        elif scan_count == 1:
            return 3
        elif scan_count == 2:
            return 1
        else:
            return 0  # 3+ clean scans = probably safe
