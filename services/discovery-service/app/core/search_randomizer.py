"""Smart search parameter randomization for diverse discovery.

Randomizes YouTube search parameters to avoid getting the same results every day:
- Order rotation (date/viewCount/rating/relevance)
- Time window rotation (last_7d, last_30d, 30-90d_ago)
- Deep pagination (go 5 pages deep for comprehensive coverage)

Key insight: Same keyword + different order = completely different top 250 results!
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class SearchOrder(str, Enum):
    """YouTube API order parameters."""

    DATE = "date"  # Chronological - finds newest content
    VIEW_COUNT = "viewCount"  # Most viewed - finds viral content
    RATING = "rating"  # Highest rated - finds quality content
    RELEVANCE = "relevance"  # Best matches - finds most relevant content


@dataclass
class TimeWindow:
    """Time window for search filtering."""

    name: str
    days_ago_start: int  # Start of window (days from now)
    days_ago_end: int    # End of window (days from now, 0 = today)

    def get_published_after(self) -> str:
        """Get publishedAfter parameter (ISO 8601)."""
        dt = datetime.now(timezone.utc) - timedelta(days=self.days_ago_start)
        return dt.isoformat().replace("+00:00", "Z")

    def get_published_before(self) -> str:
        """Get publishedBefore parameter (ISO 8601)."""
        if self.days_ago_end == 0:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        dt = datetime.now(timezone.utc) - timedelta(days=self.days_ago_end)
        return dt.isoformat().replace("+00:00", "Z")


# Time windows - 2 months for broader coverage (duplicates are OK with multi-config subscriptions!)
TIME_WINDOWS = [
    TimeWindow(name="last_60_days", days_ago_start=60, days_ago_end=0),
    TimeWindow(name="last_30_days", days_ago_start=30, days_ago_end=0),
]

# Keywords loaded from Firestore config collection - NO LEGACY FILES!


@dataclass
class SearchParams:
    """Parameters for a single YouTube search."""

    query: str
    order: SearchOrder
    published_after: str
    published_before: str
    max_results: int = 50  # Always use max for efficiency
    page_number: int = 1   # 1-5 for deep pagination


class SearchRandomizer:
    """
    Generates diverse search parameters using daily rotation.

    Strategy:
    - 21 keywords × 1 page = ~100 queries with 10k quota
    - Each day uses different order for variety
    - 1 page per keyword maximizes keyword coverage
    - Recent time windows (last 7-14 days) for fresh content
    - Rotation prevents duplicate results across days
    """

    def __init__(self, keywords: list[str] | None = None, firestore_client=None):
        """
        Initialize search randomizer.

        Args:
            keywords: Custom keyword list (defaults to loading from Firestore)
            firestore_client: Firestore client to load config from
        """
        self.firestore = firestore_client  # Store for search history queries

        if keywords:
            self.keywords = keywords
        else:
            # Load from Firestore config
            self.keywords = self._load_keywords_from_firestore(firestore_client)

        self.orders = list(SearchOrder)
        self.time_windows = TIME_WINDOWS

        logger.info(
            f"SearchRandomizer initialized: {len(self.keywords)} keywords from Firestore, "
            f"{len(self.orders)} orders, {len(self.time_windows)} time windows"
        )

    def _load_keywords_from_firestore(self, firestore_client) -> list[str]:
        """Load keywords from Firestore ip_configs collection."""
        if not firestore_client:
            logger.error("No Firestore client provided, using empty keyword list")
            return []

        try:
            # Load from ip_configs collection
            logger.debug("Loading keywords from ip_configs collection...")
            configs = list(firestore_client.collection("ip_configs").stream())
            logger.debug(f"Found {len(configs)} configs in ip_configs collection")

            keywords = []
            for doc in configs:
                config_data = doc.to_dict()
                logger.debug(f"Config {doc.id}: name={config_data.get('name')}, deleted={config_data.get('deleted', False)}, has_search_keywords={bool(config_data.get('search_keywords'))}")

                # Skip deleted configs
                if config_data.get("deleted", False):
                    logger.debug(f"  Skipping deleted config: {config_data.get('name')}")
                    continue

                # Get search_keywords field
                search_keywords = config_data.get("search_keywords", [])
                if search_keywords:
                    keywords.extend(search_keywords)
                    logger.info(
                        f"  📋 Loaded {len(search_keywords)} keywords for '{config_data.get('name')}'"
                    )
                else:
                    logger.debug(f"  No search_keywords for config: {config_data.get('name')}")

            logger.info(f"✅ Loaded {len(keywords)} total keywords from Firestore")
            return keywords

        except Exception as e:
            logger.error(f"Failed to load keywords from Firestore: {e}", exc_info=True)
            return []

    def _prioritize_keywords(self, max_keywords: int) -> list[str]:
        """
        Prioritize keywords by tier and search history.

        Priority order:
        1. Tier 1 never-searched (highest ROI + initial data)
        2. Tier 1 past cooldown (proven efficiency)
        3. Tier 2 never-searched
        4. Tier 2 past cooldown
        5. Tier 3 never-searched
        6. Tier 3 past cooldown

        Args:
            max_keywords: Maximum number of keywords to select

        Returns:
            List of prioritized keywords
        """
        if not self.firestore:
            logger.warning("No Firestore client, using first N keywords without prioritization")
            return self.keywords[:max_keywords]

        try:
            # Get search history for all keywords
            search_history = {}
            tier_map = {}

            # Load all keyword search records
            keyword_docs = list(self.firestore.collection("keyword_searches").stream())

            # Build search history map
            for doc in keyword_docs:
                data = doc.to_dict()
                keyword = data.get("keyword")
                if keyword not in search_history:
                    search_history[keyword] = {
                        "last_searched": data.get("searched_at"),
                        "tier": data.get("tier", 3),  # Default to Tier 3 if missing
                    }

            # Assign default tier for never-searched keywords
            for keyword in self.keywords:
                if keyword not in search_history:
                    search_history[keyword] = {
                        "last_searched": None,  # Never searched!
                        "tier": 3,  # Start at Tier 3, will upgrade based on efficiency
                    }
                tier_map[keyword] = search_history[keyword]["tier"]

            # Sort by: tier (ascending), never_searched (True first), last_searched (oldest first)
            def sort_key(keyword):
                info = search_history[keyword]
                tier = info["tier"]
                # Convert tier to int for sorting (handle both int and str)
                tier_int = int(tier) if isinstance(tier, (int, str)) else 3
                never_searched = info["last_searched"] is None
                last_searched = info["last_searched"] or datetime.min.replace(tzinfo=timezone.utc)

                # Return tuple: (tier, not never_searched, last_searched)
                # - Lower tier = higher priority
                # - never_searched=True → not never_searched=False → higher priority
                # - Older last_searched → higher priority
                return (tier_int, not never_searched, last_searched)

            sorted_keywords = sorted(self.keywords, key=sort_key)

            # Take top N
            selected = sorted_keywords[:max_keywords]

            # Log selection breakdown
            tier_counts = {}
            never_searched_count = 0
            for kw in selected:
                tier = search_history[kw]["tier"]
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                if search_history[kw]["last_searched"] is None:
                    never_searched_count += 1

            logger.info(
                f"🎯 Selected {len(selected)}/{len(self.keywords)} keywords by priority: "
                f"Tier 1={tier_counts.get(1, 0)}, Tier 2={tier_counts.get(2, 0)}, Tier 3={tier_counts.get(3, 0)}, "
                f"Never-searched={never_searched_count}"
            )

            return selected

        except Exception as e:
            logger.error(f"Failed to prioritize keywords: {e}", exc_info=True)
            logger.warning("Falling back to first N keywords")
            return self.keywords[:max_keywords]

    def get_daily_search_plan(
        self,
        max_quota: int = 10_000,
        pages_per_keyword: int = 1,  # Not used anymore - we try all 4 orderings
    ) -> list[SearchParams]:
        """
        Generate full search plan for the day.

        NEW STRATEGY:
        1. CHANNEL SCANNING (10 quota): Scan channels with known infringements
        2. RANDOMIZED KEYWORD SEARCH (rest of quota): Random keyword + ordering
           - Tier-weighted keyword selection (Tier 1 more likely than Tier 3)
           - Only exhaust when a keyword+order returns < 50 videos

        Tier probabilities:
        - Tier 1: 50% probability
        - Tier 2: 35% probability
        - Tier 3: 15% probability

        Args:
            max_quota: Maximum quota units (default: 10,000)
            pages_per_keyword: Ignored (kept for API compatibility)

        Returns:
            List of search parameters with channel scans first, then randomized keywords
        """
        import random

        # Get channels to scan (if Firestore available)
        channels_to_scan = []
        if self.firestore:
            channels_to_scan = self._get_channels_to_scan(max_channels=5)  # 5 channels = 10 quota

        # Allocate quota: reserve for channels only if we have channels to scan
        if channels_to_scan:
            channel_quota = len(channels_to_scan) * 2  # Each channel = 2 units
            keyword_quota = max_quota - channel_quota
            logger.info(
                f"🔄 HYBRID STRATEGY: Channel tracking ({len(channels_to_scan)} most active channels = {channel_quota} quota) + Randomized keywords ({keyword_quota} quota)"
            )
            logger.info(f"📺 Scanning {len(channels_to_scan)} channels with most videos")
        else:
            channel_quota = 0
            keyword_quota = max_quota
            logger.info(
                f"🔄 KEYWORD-ONLY STRATEGY: No channels to scan, using all {keyword_quota} quota for keywords"
            )
            logger.info(f"📺 No channels with infringements found yet")

        # Get all keywords grouped by tier
        if not self.firestore:
            logger.warning("No Firestore client, using simple keyword list")
            keywords_by_tier = {1: self.keywords, 2: [], 3: []}
        else:
            keywords_by_tier = self._get_keywords_by_tier()

        # Calculate how many keyword queries we can make
        max_queries = keyword_quota // 100  # Each query = 100 units

        logger.info(
            f"📊 Tier distribution: Tier 1={len(keywords_by_tier.get(1, []))}, "
            f"Tier 2={len(keywords_by_tier.get(2, []))}, Tier 3={len(keywords_by_tier.get(3, []))}"
        )
        logger.info(f"📊 Will generate {max_queries} randomized keyword queries")

        # All-time search (no date filter)
        now = datetime.now(timezone.utc)
        published_after = None  # All time!
        published_before = now.isoformat().replace("+00:00", "Z")

        # Start with channel scans (these go first for priority)
        search_plan = []

        for channel in channels_to_scan:
            params = SearchParams(
                query="",  # Empty query means channel scan
                order=SearchOrder.DATE,  # Most recent uploads
                published_after="",
                published_before=published_before,
                max_results=50,
                page_number=1,
            )
            # Store channel_id in query field temporarily (will be handled by discovery_engine)
            params.query = f"CHANNEL:{channel['channel_id']}"
            search_plan.append(params)
            logger.debug(f"  📺 Added channel scan: {channel['channel_id']} ({channel['video_count']} videos)")

        # Generate randomized keyword search plan
        seen_combinations = set()  # Track keyword+order to avoid duplicates

        # Tier weights (probability of selecting each tier)
        tier_weights = {1: 0.50, 2: 0.35, 3: 0.15}

        # Keep trying until we have max_queries unique KEYWORD queries
        # (channel scans are already in search_plan, so track keywords separately)
        keyword_queries_added = 0
        attempts = 0
        max_attempts = max_queries * 10  # Prevent infinite loop

        while keyword_queries_added < max_queries and attempts < max_attempts:
            attempts += 1

            # Randomly select tier (weighted)
            available_tiers = [t for t in [1, 2, 3] if keywords_by_tier.get(t, [])]
            if not available_tiers:
                logger.warning("No keywords available in any tier!")
                break

            # Weighted random tier selection
            tier_probs = [tier_weights[t] for t in available_tiers]
            tier = random.choices(available_tiers, weights=tier_probs, k=1)[0]

            # Randomly select keyword from that tier
            keywords_in_tier = keywords_by_tier[tier]
            keyword = random.choice(keywords_in_tier)

            # Randomly select ordering
            order = random.choice(self.orders)

            # Check if we've already added this combination
            combo_key = f"{keyword}|{order.value}"
            if combo_key in seen_combinations:
                # Skip duplicate, keep trying
                continue
            seen_combinations.add(combo_key)

            params = SearchParams(
                query=keyword,
                order=order,
                published_after=published_after or "",  # Empty string = all time
                published_before=published_before,
                max_results=50,
                page_number=1,
            )
            search_plan.append(params)
            keyword_queries_added += 1

        if attempts >= max_attempts:
            logger.warning(f"Reached max attempts ({max_attempts}) generating queries. Got {keyword_queries_added}/{max_queries} keyword queries")

        # Shuffle the plan for extra randomness
        random.shuffle(search_plan)

        # Calculate totals
        num_channels = len(channels_to_scan)
        num_keywords = keyword_queries_added
        total_queries = num_channels + num_keywords
        total_quota = (num_channels * 2) + (num_keywords * 100)

        logger.info(
            f"📊 Search plan generated: {total_queries} queries "
            f"({num_channels} channels + {num_keywords} keywords), "
            f"{total_quota} quota units"
        )
        logger.info(f"📅 Time: ALL TIME (no filter)")
        logger.info(f"🎲 Random ordering with tier weighting: T1=50%, T2=35%, T3=15%")

        return search_plan

    def _get_keywords_by_tier(self) -> dict[int, list[str]]:
        """
        Get keywords grouped by tier from search history.

        Returns:
            Dict mapping tier (1, 2, 3) to list of keywords
        """
        try:
            # Get search history for all keywords
            keyword_docs = list(self.firestore.collection("keyword_searches").stream())

            # Build map of keyword → tier (use latest tier)
            keyword_tiers = {}
            seen_keywords = set()

            for doc in keyword_docs:
                data = doc.to_dict()
                keyword = data.get("keyword")

                # Only use latest record per keyword
                if keyword in seen_keywords:
                    continue
                seen_keywords.add(keyword)

                tier = data.get("tier", "3")  # Default to Tier 3
                tier_int = int(tier) if isinstance(tier, (int, str)) else 3
                keyword_tiers[keyword] = tier_int

            # Assign Tier 3 to never-searched keywords
            for keyword in self.keywords:
                if keyword not in keyword_tiers:
                    keyword_tiers[keyword] = 3  # Start at lowest tier

            # Group by tier
            by_tier = {1: [], 2: [], 3: []}
            for keyword, tier in keyword_tiers.items():
                if tier in by_tier:
                    by_tier[tier].append(keyword)

            return by_tier

        except Exception as e:
            logger.error(f"Failed to get keywords by tier: {e}", exc_info=True)
            # Fallback: all keywords in Tier 3
            return {1: [], 2: [], 3: self.keywords}

    def _get_channels_to_scan(self, max_channels: int = 10) -> list[dict]:
        """
        Get channels that need scanning.

        Priority:
        1. Channels with most videos (high activity)
        2. Channels not scanned recently (> 7 days)

        Args:
            max_channels: Maximum number of channels to scan (default: 10)

        Returns:
            List of channel dicts with channel_id and video_count
        """
        try:
            from datetime import timedelta

            # Query ALL videos to find most active channels
            videos_query = self.firestore.collection("videos").stream()

            # Count videos per channel
            channel_video_counts = {}
            for video in videos_query:
                data = video.to_dict()
                channel_id = data.get("channel_id")
                if channel_id:
                    channel_video_counts[channel_id] = channel_video_counts.get(channel_id, 0) + 1

            if not channel_video_counts:
                logger.info("📺 No channels found yet")
                return []

            # Get channel scan history
            scan_history = {}
            channel_scans = self.firestore.collection("channel_scans").stream()
            for doc in channel_scans:
                data = doc.to_dict()
                channel_id = data.get("channel_id")
                last_scanned = data.get("last_scanned_at")
                if channel_id and last_scanned:
                    scan_history[channel_id] = last_scanned

            # Filter out recently scanned channels (< 7 days ago)
            now = datetime.now(timezone.utc)
            min_scan_interval = timedelta(days=7)
            channels_to_scan = []

            for channel_id, video_count in channel_video_counts.items():
                last_scanned = scan_history.get(channel_id)

                # Skip if scanned recently
                if last_scanned:
                    if isinstance(last_scanned, str):
                        last_scanned = datetime.fromisoformat(last_scanned.replace('Z', '+00:00'))

                    time_since_scan = now - last_scanned.replace(tzinfo=timezone.utc)
                    if time_since_scan < min_scan_interval:
                        logger.debug(f"  ⏭️  Skipping {channel_id}: scanned {time_since_scan.days}d ago")
                        continue

                channels_to_scan.append({
                    "channel_id": channel_id,
                    "video_count": video_count,
                })

            # Sort by video count (descending) - most active channels first
            channels_to_scan.sort(key=lambda x: x["video_count"], reverse=True)

            # Take top N
            top_channels = channels_to_scan[:max_channels]

            logger.info(f"📺 Selected {len(top_channels)} channels to scan (from {len(channel_video_counts)} total channels)")
            for ch in top_channels[:5]:  # Log top 5
                logger.info(f"  📺 {ch['channel_id']}: {ch['video_count']} videos")

            return top_channels

        except Exception as e:
            logger.error(f"Failed to get channels to scan: {e}", exc_info=True)
            return []

    def get_search_params_for_index(
        self,
        index: int,
        day_offset: int = 0,
        pages_per_keyword: int = 5,
    ) -> SearchParams:
        """
        Get search parameters for a specific query index.

        Useful for distributed execution where each worker handles
        a subset of queries.

        Args:
            index: Query index (0 to num_queries-1)
            day_offset: Days from today (0=today, 1=tomorrow, etc.)
            pages_per_keyword: Pages to fetch per keyword

        Returns:
            Search parameters for this index
        """
        # Calculate which keyword and page this index represents
        keyword_idx = index // pages_per_keyword
        page_number = (index % pages_per_keyword) + 1

        if keyword_idx >= len(self.keywords):
            raise ValueError(f"Index {index} exceeds keyword range")

        keyword = self.keywords[keyword_idx]

        # Get rotation for this day
        day_of_year = (datetime.now(timezone.utc) + timedelta(days=day_offset)).timetuple().tm_yday
        order_idx = day_of_year % len(self.orders)
        window_idx = (day_of_year // len(self.orders)) % len(self.time_windows)

        order = self.orders[order_idx]
        time_window = self.time_windows[window_idx]

        return SearchParams(
            query=keyword,
            order=order,
            published_after=time_window.get_published_after(),
            published_before=time_window.get_published_before(),
            max_results=50,
            page_number=page_number,
        )

    def estimate_daily_capacity(
        self,
        quota: int = 10_000,
        pages_per_keyword: int = 5,
    ) -> dict[str, int]:
        """
        Estimate how many videos can be discovered with given quota.

        Args:
            quota: Daily quota units
            pages_per_keyword: Pages per keyword

        Returns:
            Capacity estimates
        """
        quota_per_keyword = pages_per_keyword * 100  # Each page = 100 units
        max_keywords = quota // quota_per_keyword
        total_queries = max_keywords * pages_per_keyword
        max_videos = total_queries * 50  # Each query returns up to 50 videos

        return {
            "quota": quota,
            "max_keywords": max_keywords,
            "queries_per_day": total_queries,
            "potential_videos": max_videos,
            "quota_utilization": min(total_queries * 100, quota),
        }
