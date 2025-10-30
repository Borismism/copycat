"""
Adaptive risk rescoring algorithm - THE CORE of risk-analyzer-service.

This is the intelligent system that continuously re-evaluates video risk
based on 5 dynamic factors, enabling adaptive Gemini budget allocation.
"""

import logging
from datetime import datetime, timezone

from google.cloud import firestore

logger = logging.getLogger(__name__)


class RiskRescorer:
    """
    Adaptive risk rescoring algorithm.

    6-Factor Dynamic Risk Model:
    1. Discovery freshness (+20 to -20) - NEW = suspicious, rescanned clean = safe
    2. View velocity (+0 to +30) - Viral detection
    3. Channel reputation (+0 to +20) - Serial infringers
    4. Engagement rate (+0 to +10) - High interaction
    5. Age decay (-15 to 0) - Old videos lose priority
    6. Prior Gemini results (-10 to +20) - Learn from analysis

    This creates a living risk score that adapts to:
    - Viral content (catch before mega-viral)
    - Bad actor channels (prioritize serial infringers)
    - Aging content (deprioritize old videos)
    - Confirmed results (boost infringements, reduce clean videos)
    """

    def __init__(self, firestore_client: firestore.Client):
        """
        Initialize risk rescorer.

        Args:
            firestore_client: Firestore client for data access
        """
        self.firestore = firestore_client
        self.videos_collection = "videos"
        self.channels_collection = "channels"
        self.velocity_snapshots_collection = "view_velocity_snapshots"

        logger.info("RiskRescorer initialized")

    def recalculate_risk(self, video_data: dict) -> dict:
        """
        Recalculate risk score for a video using 5-factor algorithm.

        Args:
            video_data: Video document from Firestore

        Returns:
            Dictionary with new risk, tier, and factor breakdown
        """
        video_id = video_data.get("video_id", "")
        initial_risk = video_data.get("initial_risk", 50)

        # Start with baseline of 50 (neutral risk)
        # The 6 factors will adjust this up or down
        risk = 50

        factors = {
            "initial": 50,
            "discovery_freshness": 0,
            "view_velocity": 0,
            "channel_reputation": 0,
            "engagement": 0,
            "age_decay": 0,
            "prior_results": 0,
        }

        # Factor 1: Discovery Freshness (+20 to -20 points)
        # NEW DISCOVERY = HIGH RISK! Scanned many times clean = LOW RISK
        freshness_boost = self._calculate_discovery_freshness(video_data)
        risk += freshness_boost
        factors["discovery_freshness"] = freshness_boost

        # Factor 2: View Velocity (0-30 points)
        velocity_boost = self._calculate_velocity_boost(video_data)
        risk += velocity_boost
        factors["view_velocity"] = velocity_boost

        # Factor 3: Channel Reputation (0-20 points)
        channel_boost = self._calculate_channel_boost(video_data)
        risk += channel_boost
        factors["channel_reputation"] = channel_boost

        # Factor 4: Engagement Rate (0-10 points)
        engagement_boost = self._calculate_engagement_boost(video_data)
        risk += engagement_boost
        factors["engagement"] = engagement_boost

        # Factor 5: Age vs Views (-15 to +15 points)
        # OLD + HIGH VIEWS = SURVIVOR = BOOST!
        age_adjustment = self._calculate_age_decay(video_data)
        risk += age_adjustment
        factors["age_decay"] = age_adjustment

        # Factor 6: Prior Analysis Results (-10 to +20 points)
        results_adjustment = self._calculate_results_adjustment(video_data)
        risk += results_adjustment
        factors["prior_results"] = results_adjustment

        # Clamp to 0-100
        new_risk = max(0, min(risk, 100))

        # Calculate tier
        new_tier = self.calculate_tier(new_risk)

        logger.info(
            f"Video {video_id}: risk {initial_risk}→{new_risk}, tier={new_tier}, "
            f"factors={factors}"
        )

        return {
            "new_risk": new_risk,
            "new_tier": new_tier,
            "factors": factors,
        }

    def _calculate_discovery_freshness(self, video_data: dict) -> int:
        """
        Factor 1: Discovery freshness boost/penalty (+20 to -20 points).

        YOUR BRILLIANT INSIGHT: Just finding a video is SUSPICIOUS!

        Logic:
        - NEVER SCANNED (new discovery): +20 points (HIGH RISK - investigate!)
        - Scanned 1 time, clean: +10 points (still suspicious, rescan)
        - Scanned 2 times, clean: 0 points (neutral)
        - Scanned 3+ times, clean: -10 points (probably safe)
        - Scanned 5+ times, clean: -20 points (confirmed clean)
        - Scanned any times, INFRINGEMENT FOUND: +20 points (known bad!)

        This inverts the old logic: NEW = risky, RESCANNED CLEAN = safe
        """
        scan_count = video_data.get("scan_count", 0)
        gemini_result = video_data.get("gemini_result")  # "clean", "infringement", or None

        # If Gemini found infringement, ALWAYS high risk
        if gemini_result == "infringement":
            return +20

        # Based on how many times we've scanned it clean
        if scan_count == 0:
            # NEW DISCOVERY = SUSPICIOUS!
            return +20
        elif scan_count == 1:
            # Scanned once, clean = still somewhat suspicious
            return +10
        elif scan_count == 2:
            # Scanned twice, clean = neutral
            return 0
        elif scan_count >= 5:
            # Scanned 5+ times, always clean = probably safe
            return -20
        else:  # scan_count 3-4
            # Scanned 3-4 times, clean = likely safe
            return -10

    def _calculate_velocity_boost(self, video_data: dict) -> int:
        """
        Factor 1: View velocity bonus (0-30 points).

        Viral detection - videos gaining views rapidly get priority.
        This catches content going viral BEFORE it hits millions.

        Thresholds:
        - >10k views/hour: +30 (extremely viral)
        - >1k views/hour: +20 (very viral)
        - >100 views/hour: +10 (viral)
        - Otherwise: 0
        """
        view_velocity = video_data.get("view_velocity", 0.0)

        if view_velocity > 10_000:
            return 30
        elif view_velocity > 1_000:
            return 20
        elif view_velocity > 100:
            return 10
        else:
            return 0

    def _calculate_channel_boost(self, video_data: dict) -> int:
        """
        Factor 2: Channel reputation bonus (0-20 points).

        Serial infringers get maximum priority. If a channel has been
        confirmed to infringe before, their new videos are HIGH priority.

        Thresholds:
        - >50% infringement rate: +20 (serial infringer)
        - >25% infringement rate: +10 (frequent infringer)
        - Otherwise: 0
        """
        # Try to get channel risk from video data
        # In production, would fetch from channels collection
        channel_risk = video_data.get("channel_risk", 0)

        # Convert channel_risk (0-100) to boost (0-20)
        # Simple linear mapping: risk/100 * 20
        return min(int(channel_risk * 0.2), 20)

    def _calculate_engagement_boost(self, video_data: dict) -> int:
        """
        Factor 3: Engagement rate bonus (0-10 points).

        High engagement (likes, comments) suggests the video is being
        watched and shared - higher impact if it's infringing.

        Thresholds:
        - >5% engagement rate: +10
        - >2% engagement rate: +5
        - Otherwise: 0
        """
        view_count = video_data.get("view_count", 0)
        if view_count == 0:
            return 0

        like_count = video_data.get("like_count", 0)
        comment_count = video_data.get("comment_count", 0)

        engagement_rate = (like_count + comment_count) / view_count

        if engagement_rate > 0.05:
            return 10
        elif engagement_rate > 0.02:
            return 5
        else:
            return 0

    def _calculate_age_decay(self, video_data: dict) -> int:
        """
        Factor 5: Age vs Views adjustment (-15 to +15 points).

        BRILLIANT USER INSIGHT: High views + old = SURVIVOR = HIGH RISK!

        Logic:
        - Old + High Views = Slipped through moderation, causing damage = BOOST
        - Old + Low Views = Nobody saw it = PENALTY
        - New = Always urgent = No penalty

        Adjustments:
        - >6 months old + >100k views: +15 (SURVIVOR - still up and popular!)
        - >3 months old + >50k views: +10 (popular old video)
        - >1 month old + >10k views: +5 (moderately popular)
        - Old + Low views: -15 to -5 (not urgent)
        """
        published_at = video_data.get("published_at")
        view_count = video_data.get("view_count", 0)

        if not published_at:
            return 0

        # Handle both datetime objects and timestamps
        if isinstance(published_at, datetime):
            pub_date = published_at
        else:
            pub_date = published_at

        age_days = (datetime.now(timezone.utc) - pub_date).days

        # Recent videos = no adjustment (always urgent)
        if age_days <= 7:
            return 0

        # OLD + HIGH VIEWS = SURVIVOR BIAS = HIGH RISK!
        if age_days > 180:  # >6 months old
            if view_count > 100000:
                return +15  # Still up with 100k+ views = BIG PROBLEM!
            elif view_count > 10000:
                return +5   # Still up with 10k+ views = problem
            else:
                return -15  # Old and unpopular = low priority

        elif age_days > 90:  # >3 months old
            if view_count > 50000:
                return +10  # Popular after 3 months = likely slipped through
            elif view_count > 5000:
                return +3
            else:
                return -10  # Old and unpopular

        elif age_days > 30:  # >1 month old
            if view_count > 10000:
                return +5   # Popular after a month
            else:
                return -5   # Old and unpopular

        else:
            return 0

    def _calculate_results_adjustment(self, video_data: dict) -> int:
        """
        Factor 5: Prior analysis results adjustment (-10 to +20 points).

        Learn from Gemini results:
        - Confirmed infringement: +20 (boost follow-up)
        - Confirmed clean: -10 (reduce priority)

        This creates a feedback loop where the system learns which
        content types are actually infringing.
        """
        # Check for gemini_result field
        gemini_result = video_data.get("gemini_result")
        if not gemini_result:
            return 0

        # Check if it's confirmed infringement
        contains_infringement = gemini_result.get("contains_infringement", False)

        if contains_infringement:
            return 20  # Confirmed infringer - max boost
        else:
            return -10  # Confirmed clean - reduce priority

    def calculate_tier(self, risk: int) -> str:
        """
        Calculate risk tier from score.

        Tiers determine scan frequency:
        - CRITICAL (90-100): Scan within 6 hours
        - HIGH (70-89): Scan within 24 hours
        - MEDIUM (40-69): Scan within 72 hours
        - LOW (20-39): Scan within 7 days
        - VERY_LOW (0-19): Scan within 30 days

        Args:
            risk: Risk score (0-100)

        Returns:
            Risk tier string
        """
        if risk >= 90:
            return "CRITICAL"
        elif risk >= 70:
            return "HIGH"
        elif risk >= 40:
            return "MEDIUM"
        elif risk >= 20:
            return "LOW"
        else:
            return "VERY_LOW"

    def batch_rescore(self, video_ids: list[str]) -> dict[str, dict]:
        """
        Rescore multiple videos efficiently.

        Args:
            video_ids: List of video IDs to rescore

        Returns:
            Dictionary mapping video_id to rescore results
        """
        results = {}

        for video_id in video_ids:
            try:
                # Fetch video from Firestore
                doc_ref = self.firestore.collection(self.videos_collection).document(
                    video_id
                )
                doc = doc_ref.get()

                if not doc.exists:
                    logger.warning(f"Video {video_id} not found")
                    continue

                video_data = doc.to_dict()

                # Recalculate risk
                rescore_result = self.recalculate_risk(video_data)
                results[video_id] = rescore_result

                # Update Firestore
                old_risk = video_data.get("current_risk", None)
                new_risk = rescore_result["new_risk"]

                logger.info(f"Video {video_id}: old_risk={old_risk}, new_risk={new_risk}, will_update={old_risk is None or old_risk != new_risk}")

                # Always update if current_risk doesn't exist OR if value changed
                if old_risk is None or old_risk != new_risk:
                    doc_ref.update({
                        "current_risk": new_risk,
                        "risk_tier": rescore_result["new_tier"],
                        "last_risk_update": datetime.now(timezone.utc),
                    })

                    logger.info(
                        f"Video {video_id}: risk updated {old_risk}→{new_risk} "
                        f"(tier={rescore_result['new_tier']}, factors={rescore_result['factors']})"
                    )

            except Exception as e:
                logger.error(f"Error rescoring video {video_id}: {e}")
                continue

        return results
