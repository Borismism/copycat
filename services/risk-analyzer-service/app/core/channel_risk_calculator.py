"""
Channel Risk Calculator - Infringement-Based Scoring

Channel risk = infringement percentage + absolute count + reach (only if infringing)

KEY INSIGHT: Reach only matters IF the channel has infringements.
- Big channel, 0 infringements = LOW risk
- Small channel, 50% infringement = MEDIUM risk
- Big channel, 50% infringement = HIGH risk (reach amplifies)

Scoring (0-100):
1. Infringement Rate (0-50 pts) - What % of their videos infringe
2. Absolute Volume (0-30 pts) - How many total infringements
3. Channel Reach (0-20 pts) - ONLY if infringement rate > 0
"""

import logging

logger = logging.getLogger(__name__)


class ChannelRiskCalculator:
    """Calculate channel risk based on infringement history."""

    def calculate_channel_risk(self, channel: dict) -> dict:
        """
        Calculate channel risk score.

        Formula:
        - Base: Infringement rate (0-50) + absolute count (0-30)
        - Multiplier: Reach (0-20) ONLY applies if infringement_rate > 0

        Args:
            channel: Channel document from Firestore

        Returns:
            {
                "channel_risk": int (0-100),
                "factors": dict,
                "stats": dict
            }
        """
        channel_id = channel.get("channel_id", "unknown")

        # Get infringement data
        confirmed = channel.get("confirmed_infringements", 0)
        total_scanned = channel.get("total_videos_analyzed", channel.get("total_videos_found", 0))
        subscriber_count = channel.get("subscriber_count", 0)

        # No data yet = unknown, low risk
        if total_scanned == 0:
            logger.info(f"Channel {channel_id}: risk=0 (no videos scanned yet)")
            return {
                "channel_risk": 0,
                "factors": {"infringement_rate": 0, "infringement_volume": 0, "reach": 0},
                "stats": {"confirmed_infringements": 0, "total_videos_scanned": 0, "rate_percentage": 0.0}
            }

        # Calculate infringement rate
        rate = confirmed / total_scanned
        rate_pct = rate * 100

        # 1. INFRINGEMENT RATE (0-50 points)
        if rate <= 0:
            rate_points = 0
        elif rate <= 0.10:
            # 0-10% → 0-12 points
            rate_points = int(rate * 120)
        elif rate <= 0.25:
            # 10-25% → 12-25 points
            rate_points = 12 + int((rate - 0.10) * 87)
        elif rate <= 0.50:
            # 25-50% → 25-38 points
            rate_points = 25 + int((rate - 0.25) * 52)
        elif rate <= 0.75:
            # 50-75% → 38-45 points
            rate_points = 38 + int((rate - 0.50) * 28)
        else:
            # 75-100% → 45-50 points
            rate_points = 45 + int((rate - 0.75) * 20)

        rate_points = min(50, rate_points)

        # 2. ABSOLUTE VOLUME (0-30 points)
        if confirmed == 0:
            volume_points = 0
        elif confirmed == 1:
            volume_points = 4   # First offense
        elif confirmed <= 3:
            volume_points = 8   # 2-3 infringements
        elif confirmed <= 5:
            volume_points = 12  # 4-5 infringements
        elif confirmed <= 10:
            volume_points = 18  # 6-10 infringements
        elif confirmed <= 20:
            volume_points = 24  # 11-20 infringements
        else:
            volume_points = 30  # 20+ infringements (serial infringer)

        # 3. CHANNEL REACH (0-20 points) - ONLY if there are infringements
        if confirmed == 0:
            reach_points = 0  # No infringements = reach doesn't matter
        else:
            # Reach amplifies risk for channels WITH infringements
            if subscriber_count >= 1_000_000:
                reach_points = 20  # 1M+ subs
            elif subscriber_count >= 500_000:
                reach_points = 16  # 500k+
            elif subscriber_count >= 100_000:
                reach_points = 12  # 100k+
            elif subscriber_count >= 50_000:
                reach_points = 9   # 50k+
            elif subscriber_count >= 10_000:
                reach_points = 6   # 10k+
            elif subscriber_count >= 1_000:
                reach_points = 3   # 1k+
            else:
                reach_points = 0   # Small channel

        # TOTAL
        channel_risk = rate_points + volume_points + reach_points
        channel_risk = max(0, min(100, channel_risk))

        logger.info(
            f"Channel {channel_id}: risk={channel_risk} | "
            f"{confirmed}/{total_scanned} = {rate_pct:.1f}% infringement | "
            f"{subscriber_count:,} subs | "
            f"rate={rate_points}, vol={volume_points}, reach={reach_points}"
        )

        return {
            "channel_risk": channel_risk,
            "factors": {
                "infringement_rate": rate_points,
                "infringement_volume": volume_points,
                "reach": reach_points
            },
            "stats": {
                "confirmed_infringements": confirmed,
                "total_videos_scanned": total_scanned,
                "rate_percentage": round(rate_pct, 1),
                "subscriber_count": subscriber_count
            }
        }

    def get_channel_tier(self, channel_risk: int) -> str:
        """
        Get channel tier based on risk score.

        Tiers determine scan frequency for new videos from this channel.
        """
        if channel_risk >= 70:
            return "HIGH_RISK"      # Scan all videos immediately
        elif channel_risk >= 40:
            return "MEDIUM_RISK"    # Scan within 24h
        elif channel_risk >= 15:
            return "LOW_RISK"       # Normal priority
        else:
            return "UNKNOWN"        # New/clean channel
