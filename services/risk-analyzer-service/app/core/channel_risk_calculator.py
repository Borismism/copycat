"""
Channel Risk Calculator - 5-Factor Scoring (0-100)

Calculates channel-level risk based on historical infringement behavior.
This score represents 40% of the final scan priority.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ChannelRiskCalculator:
    """
    Calculate channel risk score (0-100) based on 5 factors.

    Factors:
    1. Infringement History (0-40 pts) - Past behavior predicts future
    2. Total Infringing Views (0-25 pts) - Scale of damage
    3. Channel Activity (0-20 pts) - Posting frequency
    4. Channel Size (0-10 pts) - Potential reach
    5. Last Infringement Recency (0-5 pts) - Urgency
    """

    def calculate_channel_risk(self, channel: dict) -> dict:
        """
        Calculate comprehensive channel risk score.

        Args:
            channel: Channel document from Firestore

        Returns:
            {
                "channel_risk": int (0-100),
                "factors": {
                    "infringement_history": int,
                    "total_infringing_views": int,
                    "channel_activity": int,
                    "channel_size": int,
                    "last_infringement_recency": int
                }
            }
        """
        channel_id = channel.get("channel_id", "unknown")

        factors = {
            "infringement_history": self._calculate_infringement_history_score(channel),
            "total_infringing_views": self._calculate_infringing_views_score(channel),
            "channel_activity": self._calculate_channel_activity_score(channel),
            "channel_size": self._calculate_channel_size_score(channel),
            "last_infringement_recency": self._calculate_last_infringement_recency_score(channel),
        }

        # Sum all factors (max 100)
        channel_risk = sum(factors.values())
        channel_risk = max(0, min(100, channel_risk))

        logger.info(
            f"Channel {channel_id}: risk={channel_risk}, factors={factors}"
        )

        return {
            "channel_risk": channel_risk,
            "factors": factors,
        }

    def _calculate_infringement_history_score(self, channel: dict) -> int:
        """
        Factor 1: Infringement history (0-40 points).

        GUILTY UNTIL PROVEN INNOCENT - Unknown channels = HIGH RISK.
        ANY CONFIRMED INFRINGEMENT = MINIMUM 35 POINTS (ensures HIGH tier)

        Scoring Logic:
        - IF confirmed infringements found:
          - 1-2 infringements: 35 pts (HIGH RISK - proven bad actor)
          - 3-5 infringements: 37 pts
          - 6-10 infringements: 39 pts
          - 11+ infringements: 40 pts (CRITICAL)

        - IF NO infringements (yet):
          - 0 scans (UNKNOWN): 40 pts ← MAX RISK until proven otherwise!
          - 1-2 clean scans: 30 pts (still highly suspicious)
          - 3-5 clean scans: 20 pts (moderately suspicious)
          - 6-10 clean scans: 10 pts (probably clean)
          - 11+ clean scans: 5 pts (proven clean, but never zero)

        Rate multiplier (only for confirmed bad channels):
        - <10% rate: 0 pts (no penalty - they're already confirmed bad)
        - 10-25% rate: +0 pts
        - 25-50% rate: +1 pt
        - >50% rate: +2 pts
        """
        infringement_count = channel.get("infringing_videos_count", 0)
        videos_scanned = channel.get("videos_scanned", 0)
        total_videos = channel.get("total_videos_found", 1)
        infringement_rate = infringement_count / total_videos if total_videos > 0 else 0

        # Base score
        if infringement_count > 0:
            # Confirmed bad channel - MINIMUM 35 points (ensures HIGH tier)
            # ANY infringement = proven bad actor = high priority
            if infringement_count <= 2:
                base = 35  # Boosted from 15 to 35
            elif infringement_count <= 5:
                base = 37  # Boosted from 25 to 37
            elif infringement_count <= 10:
                base = 39  # Boosted from 35 to 39
            else:
                base = 40

            # Rate adjustment for bad channels (smaller bonuses now)
            if infringement_rate < 0.10:
                rate_adj = 0  # No penalty - they're confirmed bad
            elif infringement_rate < 0.25:
                rate_adj = 0
            elif infringement_rate < 0.50:
                rate_adj = 1
            else:
                rate_adj = 2

            return min(40, max(35, base + rate_adj))  # Minimum 35 for any infringement
        else:
            # No infringements YET - score by how many clean scans
            # UNKNOWN = ASSUME RISKY until proven otherwise!
            if videos_scanned == 0:
                return 40  # UNKNOWN = MAX RISK (70-80 total risk)
            elif videos_scanned <= 2:
                return 30  # Still highly suspicious
            elif videos_scanned <= 5:
                return 20  # Moderately suspicious
            elif videos_scanned <= 10:
                return 10  # Probably clean
            else:
                return 5   # Proven clean (never give 0 - always some risk)

    def _calculate_infringing_views_score(self, channel: dict) -> int:
        """
        Factor 2: Total infringing views (0-25 points).

        High-view infringements = massive damage to IP.

        Scoring:
        - 0 views: 0 pts
        - 1k-10k: 5 pts
        - 10k-100k: 10 pts
        - 100k-1M: 15 pts
        - 1M-10M: 20 pts
        - 10M+: 25 pts (MEGA VIRAL)
        """
        total_views = channel.get("total_infringing_views", 0)

        if total_views == 0:
            return 0
        elif total_views < 10_000:
            return 5
        elif total_views < 100_000:
            return 10
        elif total_views < 1_000_000:
            return 15
        elif total_views < 10_000_000:
            return 20
        else:
            return 25

    def _calculate_channel_activity_score(self, channel: dict) -> int:
        """
        Factor 3: Channel activity (0-20 points).

        Active channels = ongoing threat.

        Scoring:
        - Unknown (no data): 20 pts (assume active until proven otherwise!)
        - Posted in last 7 days: 20 pts (ACTIVE!)
        - Last 30 days: 15 pts
        - Last 90 days: 10 pts
        - Last 180 days: 5 pts
        - Older: 0 pts (dormant)

        Bonus: >10 videos/month: +5 pts (capped at 20)
        """
        last_upload = channel.get("last_upload_date")
        if not last_upload:
            return 20  # Unknown = assume active (risky!)

        # Handle both datetime objects and timestamps
        if isinstance(last_upload, datetime):
            last_upload_dt = last_upload
        else:
            # Assume it's already a datetime
            last_upload_dt = last_upload

        days_since_upload = (datetime.now(timezone.utc) - last_upload_dt).days

        if days_since_upload <= 7:
            base = 20
        elif days_since_upload <= 30:
            base = 15
        elif days_since_upload <= 90:
            base = 10
        elif days_since_upload <= 180:
            base = 5
        else:
            base = 0

        # Bonus for prolific channels (capped at max 20)
        videos_per_month = channel.get("videos_per_month", 0)
        bonus = 5 if videos_per_month > 10 else 0

        return min(20, base + bonus)

    def _calculate_channel_size_score(self, channel: dict) -> int:
        """
        Factor 4: Channel size (0-10 points).

        Larger channels = wider reach if infringing.

        Scoring:
        - <1k subs: 2 pts
        - 1k-10k: 4 pts
        - 10k-100k: 6 pts
        - 100k-1M: 8 pts
        - 1M+: 10 pts (HUGE reach)
        """
        subscribers = channel.get("subscriber_count", 0)

        if subscribers < 1_000:
            return 2
        elif subscribers < 10_000:
            return 4
        elif subscribers < 100_000:
            return 6
        elif subscribers < 1_000_000:
            return 8
        else:
            return 10

    def _calculate_last_infringement_recency_score(self, channel: dict) -> int:
        """
        Factor 5: Last infringement recency (0-5 points).

        Recent infringement = likely to do it again soon.

        Scoring:
        - Last 7 days: 5 pts (VERY HOT!)
        - Last 30 days: 3 pts
        - Last 90 days: 1 pt
        - Older: 0 pts
        """
        last_infringement_date = channel.get("last_infringement_date")
        if not last_infringement_date:
            return 0

        # Handle both datetime objects and timestamps
        if isinstance(last_infringement_date, datetime):
            last_inf_dt = last_infringement_date
        else:
            last_inf_dt = last_infringement_date

        days_since = (datetime.now(timezone.utc) - last_inf_dt).days

        if days_since <= 7:
            return 5
        elif days_since <= 30:
            return 3
        elif days_since <= 90:
            return 1
        else:
            return 0
