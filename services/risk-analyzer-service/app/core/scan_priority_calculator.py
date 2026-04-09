"""
Scan Priority Calculator - Pre-scan prioritization

Decides: "Should we scan this video, and how urgently?"

This is for UNSCANNED videos only. After Gemini scans:
- Clean → infringement_risk = 0
- Infringement → Use InfringementRiskCalculator

4 Factors (0-100):
1. IP Keyword Match (0-40) - Does title/desc match our targets?
2. Channel History (0-30) - Is this channel a known infringer?
3. AI Tool Detected (0-20) - Sora, runway, kling etc in title?
4. Recency (0-10) - Newer = more urgent

Priority Tiers:
- SCAN_NOW (70-100): Queue immediately
- SCAN_SOON (40-69): Normal queue
- SCAN_LATER (20-39): Low priority
- SKIP (0-19): Don't waste Gemini budget
"""

import logging
import re
from datetime import datetime, UTC

from google.cloud import firestore

from .channel_risk_calculator import ChannelRiskCalculator
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)

# AI generation tools to detect in titles
AI_TOOLS = ["sora", "runway", "kling", "pika", "luma", "veo", "minimax", "hailuo"]

# Target characters (case-insensitive)
TARGET_CHARACTERS = [
    "superman", "batman", "wonder woman", "flash", "aquaman",
    "green lantern", "cyborg", "joker", "harley quinn", "lex luthor",
    "justice league"
]


class ScanPriorityCalculator:
    """
    Calculate scan priority for unscanned videos.

    Simple 4-factor model to decide what to scan first.
    """

    def __init__(self, firestore_client: firestore.Client):
        self.firestore = firestore_client
        self.channel_calculator = ChannelRiskCalculator()
        logger.info("ScanPriorityCalculator initialized (simplified model)")

    async def calculate_priority(self, video_data: dict) -> dict:
        """
        Calculate scan priority for a video.

        Args:
            video_data: Video document from Firestore

        Returns:
            {
                "scan_priority": int (0-100),
                "priority_tier": str (SCAN_NOW/SCAN_SOON/SCAN_LATER/SKIP),
                "channel_risk": int (0-100),
                "factors": dict
            }
        """
        video_id = video_data.get("video_id", "unknown")
        channel_id = video_data.get("channel_id", "unknown")

        # Get channel data for history check
        channel_data = await self._get_channel_data(channel_id)

        # Calculate 4 factors
        ip_match = self._calc_ip_match(video_data)
        channel_history = self._calc_channel_history(channel_data)
        ai_tool = self._calc_ai_tool(video_data)
        recency = self._calc_recency(video_data)

        factors = {
            "ip_match": ip_match,
            "channel_history": channel_history,
            "ai_tool": ai_tool,
            "recency": recency
        }

        # Sum factors
        scan_priority = sum(factors.values())
        scan_priority = max(0, min(100, scan_priority))

        # Get tier
        priority_tier = self._get_priority_tier(scan_priority)

        # Also get channel risk for reference
        channel_result = self.channel_calculator.calculate_channel_risk(channel_data)
        channel_risk = channel_result["channel_risk"]

        logger.info(
            f"Video {video_id}: scan_priority={scan_priority}, tier={priority_tier}, "
            f"factors={factors}, channel_risk={channel_risk}"
        )

        return {
            "scan_priority": scan_priority,
            "priority_tier": priority_tier,
            "channel_risk": channel_risk,
            "factors": factors
        }

    def _calc_ip_match(self, video: dict) -> int:
        """
        IP Keyword Match (0-40 points).

        Does the title/description contain our target characters + AI keywords?
        """
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()
        text = f"{title} {description}"

        # Check for target characters
        characters_found = []
        for char in TARGET_CHARACTERS:
            if re.search(r'\b' + re.escape(char) + r'\b', text):
                characters_found.append(char)

        if not characters_found:
            return 0  # No target characters = don't scan

        # Check for AI keywords
        ai_keywords = ["ai", "artificial intelligence", "generated", "ai-generated"]
        has_ai_keyword = any(
            re.search(r'\b' + re.escape(kw) + r'\b', text)
            for kw in ai_keywords
        )

        # Check for AI tools
        has_ai_tool = any(
            re.search(r'\b' + re.escape(tool) + r'\b', text)
            for tool in AI_TOOLS
        )

        # Scoring
        if len(characters_found) >= 2 and (has_ai_keyword or has_ai_tool):
            return 40  # Multiple characters + AI = max
        elif len(characters_found) >= 1 and (has_ai_keyword or has_ai_tool):
            return 35  # One character + AI = high
        elif has_ai_tool:
            return 30  # AI tool only (might be relevant)
        elif len(characters_found) >= 2:
            return 25  # Multiple characters, no AI keyword
        elif len(characters_found) >= 1 and has_ai_keyword:
            return 30  # Character + generic AI
        elif len(characters_found) >= 1:
            return 15  # Just character name (weak signal)
        else:
            return 0

    def _calc_channel_history(self, channel: dict) -> int:
        """
        Channel History (0-30 points).

        Known infringer = scan their new videos immediately.
        """
        confirmed = channel.get("confirmed_infringements", 0)
        total_scanned = channel.get("total_videos_analyzed", 0)

        if total_scanned == 0:
            return 10  # Unknown channel = moderate priority

        rate = confirmed / total_scanned

        # High infringement rate = high priority
        if rate >= 0.50:
            return 30  # 50%+ infringement rate
        elif rate >= 0.25:
            return 25  # 25-50%
        elif rate >= 0.10:
            return 18  # 10-25%
        elif confirmed >= 1:
            return 12  # Has at least one infringement
        else:
            return 5   # Clean channel = low priority

    def _calc_ai_tool(self, video: dict) -> int:
        """
        AI Tool Detected (0-20 points).

        Sora, Runway, Kling etc in title = high priority.
        """
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()
        text = f"{title} {description}"

        # Check each AI tool
        tools_found = []
        for tool in AI_TOOLS:
            if re.search(r'\b' + re.escape(tool) + r'\b', text):
                tools_found.append(tool)

        if len(tools_found) >= 2:
            return 20  # Multiple AI tools mentioned
        elif len(tools_found) == 1:
            return 15  # One AI tool
        elif "ai" in title.split() or "a.i." in title:
            return 10  # Generic AI in title
        elif "ai generated" in text or "ai-generated" in text:
            return 12  # Explicit AI generated
        else:
            return 0

    def _calc_recency(self, video: dict) -> int:
        """
        Recency (0-10 points).

        Newer videos = more urgent (catch them before they go viral).
        """
        published_at = video.get("published_at")
        if not published_at:
            return 5  # Unknown = moderate

        try:
            if isinstance(published_at, datetime):
                pub_dt = published_at
            else:
                # Assume it's a firestore timestamp
                pub_dt = published_at

            age_hours = (datetime.now(UTC) - pub_dt).total_seconds() / 3600

            if age_hours <= 24:
                return 10  # < 24 hours old
            elif age_hours <= 72:
                return 8   # 1-3 days
            elif age_hours <= 168:
                return 5   # 3-7 days
            elif age_hours <= 720:
                return 2   # 7-30 days
            else:
                return 0   # > 30 days old
        except Exception:
            return 5  # Error = moderate

    def _get_priority_tier(self, priority: int) -> str:
        """Get priority tier from score."""
        if priority >= 70:
            return "SCAN_NOW"
        elif priority >= 40:
            return "SCAN_SOON"
        elif priority >= 20:
            return "SCAN_LATER"
        else:
            return "SKIP"

    async def _get_channel_data(self, channel_id: str) -> dict:
        """Fetch channel data from Firestore."""
        try:
            channel_ref = self.firestore.collection("channels").document(channel_id)
            channel_doc = channel_ref.get()

            if channel_doc.exists:
                return channel_doc.to_dict()
            else:
                return {
                    "channel_id": channel_id,
                    "confirmed_infringements": 0,
                    "total_videos_analyzed": 0
                }
        except Exception as e:
            log_exception_json(logger, "Error fetching channel", e, channel_id=channel_id)
            return {
                "channel_id": channel_id,
                "confirmed_infringements": 0,
                "total_videos_analyzed": 0
            }
