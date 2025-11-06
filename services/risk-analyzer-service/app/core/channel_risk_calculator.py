"""
Channel Risk Calculator V3 - Business Impact Focus

Calculates channel risk based on actual damage to IP holder.
Formula: Risk = Infringement Pattern × Channel Reach × Damage

Scoring (0-100):
1. Infringement Rate (0-40 pts) - Pattern severity
2. Absolute Volume (0-30 pts) - Scale of problem
3. Channel Reach (0-20 pts) - Subscriber count
4. Damage Done (0-10 pts) - Views on infringing content

Priority: Big channels with many infringements = Maximum risk
"""

import logging

logger = logging.getLogger(__name__)


class ChannelRiskCalculator:
    """Calculate channel risk score based on business impact."""

    def calculate_channel_risk(self, channel: dict) -> dict:
        """
        Calculate risk score focused on protecting IP holder.

        Args:
            channel: Channel document from Firestore

        Returns:
            {
                "channel_risk": int (0-100),
                "factors": {
                    "infringement_rate": float,
                    "infringement_volume": int,
                    "channel_reach": int,
                    "damage_done": int
                }
            }
        """
        channel_id = channel.get("channel_id", "unknown")

        # Get data
        confirmed_infringements = channel.get("confirmed_infringements", 0)
        total_videos_scanned = channel.get("total_videos_found", 0)
        subscriber_count = channel.get("subscriber_count", 0)
        total_views = channel.get("total_views", 0)  # Sum of view_count on all discovered videos

        if total_videos_scanned == 0:
            return {
                "channel_risk": 0,
                "factors": {
                    "infringement_rate": 0,
                    "infringement_volume": 0,
                    "channel_reach": 0,
                    "damage_done": 0
                }
            }

        infringement_rate = confirmed_infringements / total_videos_scanned

        # 1. INFRINGEMENT RATE (0-40 points)
        if infringement_rate <= 0.10:
            rate_points = infringement_rate * 150  # 0-15 points
        elif infringement_rate <= 0.25:
            rate_points = 15 + (infringement_rate - 0.10) * 66.67  # 15-25 points
        elif infringement_rate <= 0.50:
            rate_points = 25 + (infringement_rate - 0.25) * 40  # 25-35 points
        elif infringement_rate <= 0.75:
            rate_points = 35 + (infringement_rate - 0.50) * 16  # 35-39 points
        else:
            rate_points = 39 + (infringement_rate - 0.75) * 4  # 39-40 points

        rate_points = min(40, round(rate_points))

        # 2. ABSOLUTE VOLUME (0-30 points)
        if confirmed_infringements <= 2:
            volume_points = 6
        elif confirmed_infringements <= 5:
            volume_points = 12
        elif confirmed_infringements <= 10:
            volume_points = 18
        elif confirmed_infringements <= 20:
            volume_points = 23
        elif confirmed_infringements <= 40:
            volume_points = 27
        else:
            volume_points = 30

        # 3. CHANNEL REACH (0-20 points) - Subscriber count
        if subscriber_count >= 1_000_000:
            reach_points = 20  # Massive channel
        elif subscriber_count >= 500_000:
            reach_points = 17  # Very large
        elif subscriber_count >= 100_000:
            reach_points = 14  # Large
        elif subscriber_count >= 50_000:
            reach_points = 11  # Medium-large
        elif subscriber_count >= 10_000:
            reach_points = 8   # Medium
        elif subscriber_count >= 1_000:
            reach_points = 4   # Small
        else:
            reach_points = 0   # Tiny/unknown

        # 4. DAMAGE DONE (0-10 points) - Views on infringing content
        # Use rough estimate: total_views * infringement_rate
        estimated_infringing_views = int(total_views * infringement_rate)

        if estimated_infringing_views >= 10_000_000:
            damage_points = 10  # 10M+ views
        elif estimated_infringing_views >= 5_000_000:
            damage_points = 9   # 5M+ views
        elif estimated_infringing_views >= 1_000_000:
            damage_points = 8   # 1M+ views
        elif estimated_infringing_views >= 500_000:
            damage_points = 6   # 500K+ views
        elif estimated_infringing_views >= 100_000:
            damage_points = 4   # 100K+ views
        elif estimated_infringing_views >= 10_000:
            damage_points = 2   # 10K+ views
        else:
            damage_points = 0   # Minimal views

        # TOTAL SCORE
        channel_risk = rate_points + volume_points + reach_points + damage_points
        channel_risk = max(0, min(100, channel_risk))

        factors = {
            "infringement_rate": rate_points,
            "infringement_volume": volume_points,
            "channel_reach": reach_points,
            "damage_done": damage_points
        }

        logger.info(
            f"Channel {channel_id}: risk={channel_risk} "
            f"(rate={rate_points}, vol={volume_points}, reach={reach_points}, damage={damage_points}) "
            f"| {confirmed_infringements}/{total_videos_scanned} infractions, "
            f"{subscriber_count:,} subs, ~{estimated_infringing_views:,} infringing views"
        )

        return {
            "channel_risk": channel_risk,
            "factors": factors,
        }
