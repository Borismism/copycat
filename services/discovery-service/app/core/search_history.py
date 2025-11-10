"""
Search history tracking to prevent duplicate searches.

Tracks all YouTube searches in Firestore and intelligently selects
time windows to avoid redundant queries.
"""

import logging
from datetime import datetime, timedelta, UTC
import random

from google.cloud import firestore

logger = logging.getLogger(__name__)


class SearchHistory:
    """Track and deduplicate YouTube searches."""

    def __init__(self, firestore_client: firestore.Client):
        self.db = firestore_client
        self.collection = self.db.collection('search_history')

    async def should_search(
        self,
        keyword: str,
        order: str,
        time_window_days: int | None = None
    ) -> tuple[bool, dict | None]:
        """
        Check if this search should be performed.

        Returns:
            (should_search, time_window_config)
            - should_search: True if we should run this search
            - time_window_config: Dict with published_after/published_before if needed
        """
        # Get recent searches for this keyword
        recent_searches = self._get_recent_searches(keyword, order, days=7)

        if not recent_searches:
            # Never searched before - do ONE all-time search
            logger.info(f"✨ NEW SEARCH: '{keyword}' (order={order}) - first all-time search")
            return True, None

        # Check if we've EVER done an all-time search
        has_done_all_time = any(not search.get('time_window') for search in recent_searches)

        if has_done_all_time:
            # All-time already done - NEVER do it again, only use time windows
            time_window = self._generate_time_window(keyword, order, recent_searches)
            logger.info(
                f"🎯 TIME WINDOW: '{keyword}' (order={order}) - "
                f"all-time done previously, using {time_window['published_after'][:10]} to {time_window['published_before'][:10]}"
            )
            return True, time_window
        else:
            # No all-time search yet, but we have some windowed searches - do all-time once
            logger.info(f"🌍 ALL-TIME: '{keyword}' (order={order}) - doing comprehensive all-time search")
            return True, None

    def _get_recent_searches(
        self,
        keyword: str,
        order: str,
        days: int = 7
    ) -> list[dict]:
        """Get recent searches for this keyword+order combination."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        searches = (
            self.collection
            .where('keyword', '==', keyword)
            .where('order', '==', order)
            .where('searched_at', '>=', cutoff)
            .order_by('searched_at', direction=firestore.Query.DESCENDING)
            .limit(20)
            .stream()
        )

        results = []
        for doc in searches:
            data = doc.to_dict()
            results.append(data)

        return results

    def _generate_time_window(
        self,
        keyword: str,
        order: str,
        recent_searches: list[dict]
    ) -> dict:
        """
        Generate INTELLIGENT random time window for search.

        Adapts window size based on keyword upload frequency.
        """
        now = datetime.now(UTC)

        # Calculate average results per day from recent searches
        avg_results_per_day = self._estimate_upload_frequency(recent_searches)

        # Calculate minimum window size to get ~25 new videos
        min_days_for_25_videos = max(7, int(25 / max(avg_results_per_day, 0.01)))

        # Determine optimal window size to get ~50 results
        if avg_results_per_day > 5:
            # High frequency: 7-21 days
            window_days = random.choice([7, 10, 14, 21])
            logger.debug(f"High frequency keyword ({avg_results_per_day:.1f} videos/day): using {window_days} day window")
        elif avg_results_per_day > 1:
            # Medium frequency: 21-60 days
            window_days = random.choice([21, 30, 45, 60])
            logger.debug(f"Medium frequency keyword ({avg_results_per_day:.1f} videos/day): using {window_days} day window")
        elif avg_results_per_day > 0.1:
            # Low frequency: 60-180 days
            window_days = random.choice([60, 90, 120, 180])
            logger.debug(f"Low frequency keyword ({avg_results_per_day:.1f} videos/day): using {window_days} day window")
        else:
            # Very low frequency: 180-365 days
            window_days = random.choice([180, 270, 365])
            logger.debug(f"Very low frequency keyword ({avg_results_per_day:.1f} videos/day): using {window_days} day window")

        # Get time since last search
        last_search = recent_searches[0] if recent_searches else None
        days_since_last_search = 999  # Default: very long time

        if last_search:
            time_since = (datetime.now(UTC) - last_search['searched_at']).total_seconds() / 86400
            days_since_last_search = int(time_since)

        # Calculate expected new videos since last search
        expected_new = avg_results_per_day * days_since_last_search

        # Calculate expected total videos (including rediscovered for virality tracking)
        avg_results_per_day * window_days

        # INTELLIGENT VIRAL DETECTION BIAS
        # Balance: NEW discovery + VIRALITY tracking (rediscovered videos)
        rand = random.random()

        if expected_new >= 15 and days_since_last_search <= 30:
            # Enough new content since last search - search "since last time"
            # Threshold: 15 new (lower than 25, because we also want virality tracking)
            days_back = random.randint(0, max(1, days_since_last_search))
            window_days = min(window_days, days_since_last_search + 1)
            logger.debug(f"🔥 SINCE LAST SEARCH: {days_since_last_search} days (~{expected_new:.0f} new + virality tracking)")
        elif rand < 0.50 and min_days_for_25_videos <= 60:
            # VIRAL TRACKING: Last 60 days (50% chance)
            # Purpose: Update view counts on recent videos for virality detection
            days_back = random.randint(0, 60)
            logger.debug(f"📈 VIRAL TRACKING: Last 60 days (~{expected_new:.0f} new + rediscovered for view tracking)")
        elif rand < 0.80:
            # Recent content: 30-365 days (30% chance)
            # Mix of new discovery + some virality tracking
            days_back = random.randint(30, 365)
            logger.debug("📅 RECENT MIX: 30-365 days ago (new discoveries + virality)")
        else:
            # Old content: 1-5 years (20% chance)
            # Pure new discovery focus
            max_days_back = 365 * 5
            days_back = random.randint(365, max_days_back)
            logger.debug("🏛️ ARCHIVE: 1-5 years ago (pure discovery)")

        # Calculate random time window
        end_date = now - timedelta(days=days_back)
        start_date = end_date - timedelta(days=window_days)

        window = {
            'published_after': start_date.strftime('%Y-%m-%dT00:00:00Z'),
            'published_before': end_date.strftime('%Y-%m-%dT23:59:59Z')
        }

        logger.info(
            f"🎲 Smart window: {window['published_after'][:10]} to "
            f"{window['published_before'][:10]} ({window_days} days, {days_back} days ago, "
            f"~{int(avg_results_per_day * window_days)} expected results)"
        )
        return window

    def _estimate_upload_frequency(self, recent_searches: list[dict]) -> float:
        """
        Estimate average videos per day for this keyword.

        Returns average results per day based on recent searches.
        """
        if not recent_searches:
            return 1.0  # Default: assume medium frequency

        total_results = 0
        total_days = 0

        for search in recent_searches[:5]:  # Look at last 5 searches
            results = search.get('results_count', 0)
            time_window = search.get('time_window')

            if time_window:
                # Calculate days in this window
                start = datetime.fromisoformat(time_window['published_after'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(time_window['published_before'].replace('Z', '+00:00'))
                days = (end - start).days

                if days > 0:
                    total_results += results
                    total_days += days
            else:
                # All-time search - assume it covered last 365 days
                if results > 0:
                    total_results += results
                    total_days += 365

        if total_days == 0:
            return 1.0

        avg = total_results / total_days
        return max(0.01, avg)  # Minimum 0.01 to avoid division issues

    def _windows_overlap(self, window1: dict, window2: dict) -> bool:
        """Check if two time windows overlap."""
        start1 = datetime.fromisoformat(window1['published_after'].replace('Z', '+00:00'))
        end1 = datetime.fromisoformat(window1['published_before'].replace('Z', '+00:00'))
        start2 = datetime.fromisoformat(window2['published_after'].replace('Z', '+00:00'))
        end2 = datetime.fromisoformat(window2['published_before'].replace('Z', '+00:00'))

        # Check if windows overlap
        return start1 <= end2 and start2 <= end1

    async def record_search(
        self,
        keyword: str,
        order: str,
        results_count: int,
        time_window: dict | None = None
    ):
        """Record a search in history."""
        doc_data = {
            'keyword': keyword,
            'order': order,
            'results_count': results_count,
            'searched_at': datetime.now(UTC),
            'time_window': time_window
        }

        # Use compound key: keyword_order_timestamp
        doc_id = f"{keyword}_{order}_{int(datetime.now(UTC).timestamp())}"
        doc_id = doc_id.replace(':', '_').replace(' ', '_')

        self.collection.document(doc_id).set(doc_data)

        logger.info(
            f"📝 Recorded search: '{keyword}' (order={order}) → {results_count} results"
        )
