"""
Infringement Risk Calculator - Post-scan damage scoring

ONLY used AFTER Gemini confirms infringement.
If no infringement → risk = 0, done.
If infringement → calculate how much damage this is causing.
"""

import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


class InfringementRiskCalculator:
    """
    Calculate damage risk for CONFIRMED infringements only.

    Clean videos get risk = 0. Period.

    For infringements, 6 factors (0-100):
    1. View Count (0-25 pts) - Current damage
    2. View Velocity (0-25 pts) - Spreading speed
    3. Channel Reach (0-20 pts) - Audience size
    4. Content Severity (0-15 pts) - How bad is the infringement
    5. Duration (0-10 pts) - Amount of infringing content
    6. Engagement (0-5 pts) - Being shared/discussed
    """

    def calculate(self, video: dict, channel: dict, gemini_result: dict | None = None) -> dict:
        """
        Calculate infringement risk score.

        Args:
            video: Video document from Firestore
            channel: Channel document from Firestore
            gemini_result: Gemini analysis result (optional, can use video.vision_analysis)

        Returns:
            {
                "infringement_risk": int (0-100, 0 if clean),
                "risk_tier": str (CRITICAL/HIGH/MEDIUM/LOW/MINIMAL/CLEAR),
                "factors": dict (breakdown, empty if clean)
            }
        """
        video_id = video.get("video_id", "unknown")

        # Check if this is actually an infringement
        is_infringement = self._check_infringement(video, gemini_result)

        if not is_infringement:
            logger.info(f"Video {video_id}: CLEAR - no infringement, risk=0")
            return {
                "infringement_risk": 0,
                "risk_tier": "CLEAR",
                "factors": {}
            }

        # Calculate damage factors
        factors = {
            "view_count": self._calc_view_count(video),
            "view_velocity": self._calc_view_velocity(video),
            "channel_reach": self._calc_channel_reach(channel),
            "content_severity": self._calc_content_severity(video, gemini_result),
            "duration": self._calc_duration(video),
            "engagement": self._calc_engagement(video),
        }

        infringement_risk = sum(factors.values())
        infringement_risk = max(0, min(100, infringement_risk))

        risk_tier = self._get_risk_tier(infringement_risk)

        logger.info(
            f"Video {video_id}: INFRINGEMENT risk={infringement_risk}, "
            f"tier={risk_tier}, factors={factors}"
        )

        return {
            "infringement_risk": infringement_risk,
            "risk_tier": risk_tier,
            "factors": factors
        }

    def _check_infringement(self, video: dict, gemini_result: dict | None) -> bool:
        """Check if video has confirmed infringement."""
        # Check gemini_result if provided
        if gemini_result:
            if gemini_result.get("contains_infringement"):
                return True
            if gemini_result.get("is_infringement"):
                return True

        # Check video's stored vision_analysis
        vision = video.get("vision_analysis", {})
        if vision.get("contains_infringement"):
            return True

        # Check status field
        if video.get("status") == "infringement":
            return True

        return False

    def _calc_view_count(self, video: dict) -> int:
        """
        View Count (0-25 pts) - Current damage level.

        More views = more people saw infringing content = higher priority.
        """
        views = video.get("view_count", 0)

        if views >= 10_000_000:
            return 25  # 10M+ MASSIVE damage
        elif views >= 1_000_000:
            return 22  # 1M+
        elif views >= 100_000:
            return 18  # 100k+
        elif views >= 10_000:
            return 12  # 10k+
        elif views >= 1_000:
            return 6   # 1k+
        else:
            return 2   # <1k still matters

    def _calc_view_velocity(self, video: dict) -> int:
        """
        View Velocity (0-25 pts) - How fast is this spreading?

        Viral infringement = URGENT action needed.
        """
        velocity = video.get("view_velocity", 0)

        if velocity >= 10_000:
            return 25  # 10k+/hr MEGA VIRAL
        elif velocity >= 1_000:
            return 20  # 1k+/hr very viral
        elif velocity >= 100:
            return 12  # 100+/hr viral
        elif velocity >= 10:
            return 5   # 10+/hr trending
        else:
            return 0   # normal

    def _calc_channel_reach(self, channel: dict) -> int:
        """
        Channel Reach (0-20 pts) - Potential audience.

        Bigger channel = more exposure = higher priority.
        """
        subs = channel.get("subscriber_count", 0)

        if subs >= 1_000_000:
            return 20  # 1M+ subs
        elif subs >= 500_000:
            return 16  # 500k+
        elif subs >= 100_000:
            return 12  # 100k+
        elif subs >= 10_000:
            return 8   # 10k+
        elif subs >= 1_000:
            return 4   # 1k+
        else:
            return 1   # small channel still counts

    def _calc_content_severity(self, video: dict, gemini_result: dict | None) -> int:
        """
        Content Severity (0-15 pts) - How bad is the infringement?

        Full character recreation vs background appearance.
        """
        # Try to get from gemini result
        if gemini_result:
            severity = gemini_result.get("severity", "").upper()
            confidence = gemini_result.get("confidence", 0)

            # High confidence + severe = max points
            if severity == "HIGH" or confidence >= 0.9:
                return 15
            elif severity == "MEDIUM" or confidence >= 0.7:
                return 10
            elif severity == "LOW" or confidence >= 0.5:
                return 5

        # Fallback: check vision_analysis
        vision = video.get("vision_analysis", {})
        if vision.get("high_confidence"):
            return 15
        elif vision.get("contains_infringement"):
            return 10  # Default for confirmed infringement

        return 5  # Minimum for any infringement

    def _calc_duration(self, video: dict) -> int:
        """
        Duration (0-10 pts) - Amount of infringing content.

        Longer = more content = higher priority.
        """
        duration = video.get("duration_seconds", 0)

        if duration >= 600:
            return 10  # 10+ min
        elif duration >= 300:
            return 8   # 5-10 min
        elif duration >= 120:
            return 5   # 2-5 min
        elif duration >= 60:
            return 3   # 1-2 min
        else:
            return 1   # <1 min

    def _calc_engagement(self, video: dict) -> int:
        """
        Engagement (0-5 pts) - Being shared/discussed.

        High engagement = spreading organically.
        """
        views = video.get("view_count", 0)
        if views == 0:
            return 0

        likes = video.get("like_count", 0)
        comments = video.get("comment_count", 0)

        engagement_rate = (likes + comments) / views

        if engagement_rate > 0.05:
            return 5  # >5%
        elif engagement_rate > 0.02:
            return 3  # 2-5%
        else:
            return 0

    def _get_risk_tier(self, risk: int) -> str:
        """Get risk tier from score."""
        if risk >= 80:
            return "CRITICAL"
        elif risk >= 60:
            return "HIGH"
        elif risk >= 40:
            return "MEDIUM"
        elif risk >= 20:
            return "LOW"
        else:
            return "MINIMAL"
