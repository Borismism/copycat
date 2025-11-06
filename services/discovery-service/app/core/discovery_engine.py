"""Smart query-based discovery engine - completely rebuilt.

NO MORE:
- Channel tracking
- Keyword tracking
- Viral snowball
- Complex tiers

YES:
- Pure query-based discovery
- Deep pagination (5 pages per keyword)
- Order rotation (different top results daily)
- Smart deduplication (skip scanned, update unscanned for virality)
- 5,000 videos/day with 10k quota
"""

import logging
from datetime import datetime, timezone

from ..models import DiscoveryStats
from .quota_manager import QuotaManager
from .search_randomizer import SearchRandomizer, SearchOrder
from .video_processor import VideoProcessor
from .youtube_client import YouTubeClient
from .search_history import SearchHistory

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    """
    Simple, smart query-based discovery.

    Strategy:
    - 20 keywords × 5 pages deep = 100 queries = 10,000 units
    - Each day uses different order (date/viewCount/rating/relevance)
    - Each day uses different time window (last_7d/last_30d/30-90d)
    - Deep pagination ensures comprehensive coverage
    - Smart dedup: skip scanned, update unscanned for virality
    """

    def __init__(
        self,
        youtube_client: YouTubeClient,
        video_processor: VideoProcessor,
        quota_manager: QuotaManager,
        search_randomizer: SearchRandomizer | None = None,
        search_history: SearchHistory | None = None,
    ):
        """
        Initialize discovery engine.

        Args:
            youtube_client: YouTube API client
            video_processor: Video processing pipeline
            quota_manager: Quota tracking
            search_randomizer: Optional custom randomizer
        """
        self.youtube = youtube_client
        self.processor = video_processor
        self.quota = quota_manager
        self.randomizer = search_randomizer or SearchRandomizer()
        self.search_history = search_history

        logger.info("DiscoveryEngine initialized (smart query-based + search history)")

    async def discover(self, max_quota: int = 10_000, progress_callback=None) -> DiscoveryStats:
        """
        Execute smart query-based discovery.

        Process:
        1. Generate daily search plan (rotated params)
        2. Execute searches with deep pagination
        3. Process videos (dedup, IP match, save)
        4. Track stats

        Args:
            max_quota: Maximum quota units to use
            progress_callback: Optional async function to call with progress updates

        Returns:
            Discovery statistics
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"=== SMART DISCOVERY (quota={max_quota}) ===")

        # Get today's search plan
        search_plan = self.randomizer.get_daily_search_plan(
            max_quota=max_quota,
            pages_per_keyword=1,  # 1 page per keyword for variety!
        )

        unique_keywords = list(set(p.query for p in search_plan))
        logger.info(
            f"📋 Search plan: {len(search_plan)} queries, "
            f"covering {len(unique_keywords)} unique keywords"
        )
        logger.info(f"🔑 Unique keywords in plan: {unique_keywords}")

        # Send plan to callback with full query details
        query_details = [
            {'keyword': p.query, 'order': p.order.value, 'time_window': 'ALL TIME'}
            for p in search_plan
        ]
        if progress_callback:
            await progress_callback({
                'type': 'plan',
                'total_queries': len(search_plan),
                'unique_keywords': unique_keywords,
                'keywords_count': len(unique_keywords),
                'query_details': query_details  # Full list of keyword+order combinations
            })

        # NEW STRATEGY: All-time searches, no time window filtering
        logger.info(f"🌍 Using ALL-TIME search (no date filters)")
        # Remove published_after override logic - we want all-time searches

        # Execute searches (group by keyword to avoid duplicates)
        videos_discovered = 0
        videos_rediscovered = 0
        videos_skipped = 0
        quota_used = 0

        # Track keyword+order combinations (NOT just keywords!)
        # Each keyword gets 4 orderings, so we track "keyword|order" as the key
        queries_processed = set()

        # NO COOLDOWN - search all keywords every time for maximum discovery!
        keywords_to_search = unique_keywords
        logger.info(f"🚀 Starting to process {len(keywords_to_search)} keywords (NO COOLDOWN) × various orderings...")

        for idx, params in enumerate(search_plan, 1):
            # Create unique key for this keyword+order combination
            query_key = f"{params.query}|{params.order.value}"

            # Skip if we already processed this keyword+order in this run
            if query_key in queries_processed:
                logger.debug(f"⏭️  Skipping '{params.query}' order={params.order.value} (already processed)")
                continue

            # Check search history to avoid duplicate searches
            logger.debug(f"Search history check: self.search_history={self.search_history is not None}, is_channel={params.query.startswith('CHANNEL:')}")
            if self.search_history and not params.query.startswith("CHANNEL:"):
                logger.info(f"🔍 Checking search history for '{params.query}' order={params.order.value}")
                should_search, time_window = await self.search_history.should_search(
                    keyword=params.query,
                    order=params.order.value
                )

                if not should_search:
                    logger.info(f"⏭️  SKIP: '{params.query}' order={params.order.value} - searched too recently")
                    continue

                # Apply intelligent time window if suggested
                if time_window:
                    logger.info(f"🎯 Applying time window: {time_window['published_after'][:10]} to {time_window['published_before'][:10]}")
                    params.published_after = time_window['published_after']
                    params.published_before = time_window['published_before']

            logger.info(f"\n{'='*80}")
            logger.info(f"🔍 QUERY {idx}/{len(search_plan)}: '{params.query}' order={params.order.value}")

            # Send query start to callback
            if progress_callback:
                await progress_callback({
                    'type': 'query_start',
                    'query_index': idx,
                    'total_queries': len(search_plan),
                    'keyword': params.query,
                    'order': params.order.value,
                    'quota_used': quota_used,
                    'max_quota': max_quota
                })

            # Check if we've already exhausted quota (check AFTER last call, not before)
            if quota_used >= max_quota:
                logger.info(f"💯 Quota fully exhausted ({quota_used}/{max_quota})")
                break

            if not self.quota.can_afford("search", 1):
                logger.info(f"Global quota exhausted")
                break

            try:
                # Check if this is a channel scan
                is_channel_scan = params.query.startswith("CHANNEL:")

                if is_channel_scan:
                    # Extract channel ID
                    channel_id = params.query.replace("CHANNEL:", "")
                    logger.info(
                        f"📺 Scanning channel: {channel_id} (fetching 50 recent uploads)"
                    )

                    # Scan channel uploads
                    results = self.youtube.get_channel_uploads(
                        channel_id=channel_id,
                        max_results=50
                    )

                    # Save channel scan to history
                    self._save_channel_scan(channel_id)

                else:
                    # Execute keyword search
                    time_info = "ALL TIME" if not params.published_after else f"{params.published_after[:10]} to {params.published_before[:10]}"
                    logger.info(
                        f"Searching: '{params.query}' "
                        f"(order={params.order.value}, window={time_info}, "
                        f"fetching 50 results)"
                    )

                    # YouTubeClient handles pagination automatically
                    # Only pass published_after if it's set (non-empty)
                    search_kwargs = {
                        "query": params.query,
                        "max_results": 50,
                        "order": params.order.value,
                    }
                    if params.published_after:
                        search_kwargs["published_after"] = params.published_after
                    if params.published_before:
                        search_kwargs["published_before"] = params.published_before

                    results = self.youtube.search_videos(**search_kwargs)

                # Count actual API calls made (youtube_client paginates internally)
                if is_channel_scan:
                    # Channel scan costs: 1 (channels.list) + 1 (playlistItems.list) = 2 units
                    search_quota = 2
                    quota_used += search_quota
                    self.quota.record_usage("channel_details", 1)  # Use channel_details operation
                    self.quota.record_usage("playlist_items", 1)  # + playlist_items
                    logger.info(f"   → Found {len(results)} videos from channel ({search_quota} quota)")
                else:
                    # Keyword search costs: 100 units per page
                    pages_fetched = (len(results) // 50) + (1 if len(results) % 50 else 0)
                    search_quota = pages_fetched * 100
                    quota_used += search_quota
                    self.quota.record_usage("search", pages_fetched)
                    logger.info(f"   → Found {len(results)} results ({pages_fetched} pages, {search_quota} quota)")

                # Get video details (enrich with statistics)
                details_batches = 0
                if results:
                    video_ids = [
                        v['id']['videoId'] if isinstance(v.get('id'), dict) else v['id']
                        for v in results
                    ]
                    # Batch video details in groups of 50
                    details_batches = (len(video_ids) // 50) + (1 if len(video_ids) % 50 else 0)
                    results = self.youtube.get_video_details(video_ids)
                    quota_used += details_batches
                    self.quota.record_usage("video_details", details_batches)
                    logger.info(f"   → Enriched with video details ({details_batches} batch calls)")

                # Process results FIRST to get accurate counts
                new_count, rediscovered_count, skipped_count = self._process_results(
                    results
                )

                videos_discovered += new_count
                videos_rediscovered += rediscovered_count
                videos_skipped += skipped_count

                # Send query results to callback with detailed breakdown
                if progress_callback:
                    callback_data = {
                        'type': 'query_result',
                        'keyword': params.query,
                        'order': params.order.value,
                        'results_count': len(results),  # Raw YouTube results
                        'new_count': new_count,  # Actually new
                        'rediscovered_count': rediscovered_count,  # Already known
                        'skipped_count': skipped_count,  # Already scanned
                        'quota_used': search_quota,
                        'total_quota_used': quota_used
                    }
                    # Include time window if present
                    if params.published_after:
                        callback_data['time_window'] = {
                            'published_after': params.published_after,
                            'published_before': params.published_before
                        }
                    await progress_callback(callback_data)

                # Record search in history (for keyword searches only)
                if self.search_history and not params.query.startswith("CHANNEL:"):
                    time_window = None
                    if params.published_after:
                        time_window = {
                            'published_after': params.published_after,
                            'published_before': params.published_before
                        }
                    await self.search_history.record_search(
                        keyword=params.query,
                        order=params.order.value,
                        results_count=len(results),
                        time_window=time_window
                    )

                logger.info(
                    f"✅ QUERY '{params.query}' order={params.order.value} COMPLETE:"
                )
                logger.info(f"   📊 Results: {new_count} new, {rediscovered_count} rediscovered, {skipped_count} already scanned")
                logger.info(f"   💰 Quota: {search_quota + details_batches} units used")
                logger.info(f"   📈 Running totals: {videos_discovered} new, {videos_rediscovered} rediscovered, {videos_skipped} skipped")

                queries_processed.add(query_key)

                # Check if we should continue with this keyword (< 50 results = exhausted)
                if len(results) < 50:
                    logger.info(f"   ⚠️  EXHAUSTED: Only {len(results)} results (< 50), won't search other orderings")
                    # Mark all other orderings for this keyword as processed too
                    for order in [SearchOrder.DATE, SearchOrder.VIEW_COUNT, SearchOrder.RATING, SearchOrder.RELEVANCE]:
                        queries_processed.add(f"{params.query}|{order.value}")

                # Save keyword search to Firestore (aggregate across all orderings)
                # We'll save once per keyword at the end, not per ordering
                # self._save_keyword_search(params.query, today, new_count, rediscovered_count, skipped_count)

            except Exception as e:
                logger.error(f"Query '{params.query}' order={params.order.value} failed: {e}", exc_info=True)
                queries_processed.add(query_key)  # Mark as processed to avoid retry
                continue

        # Aggregate results per keyword and save to Firestore
        keyword_stats = {}
        for query_key in queries_processed:
            keyword, _ = query_key.split("|")
            if keyword not in keyword_stats:
                keyword_stats[keyword] = {
                    "new": 0,
                    "rediscovered": 0,
                    "skipped": 0,
                }

        # Note: We would need to track per-keyword stats during the loop
        # For now, we'll save aggregate stats at keyword level
        for keyword in keyword_stats:
            total = keyword_stats[keyword]["new"] + keyword_stats[keyword]["rediscovered"] + keyword_stats[keyword]["skipped"]
            if total > 0:  # Only save if we actually searched this keyword
                self._save_keyword_search(
                    keyword, today,
                    keyword_stats[keyword]["new"],
                    keyword_stats[keyword]["rediscovered"],
                    keyword_stats[keyword]["skipped"]
                )

        # Calculate stats
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        efficiency = videos_discovered / quota_used if quota_used > 0 else 0

        stats = DiscoveryStats(
            videos_discovered=videos_discovered,
            videos_with_ip_match=videos_discovered,  # All are keyword-matched
            videos_skipped_duplicate=videos_skipped,
            quota_used=quota_used,
            channels_tracked=0,  # No longer tracking channels
            duration_seconds=duration,
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            f"=== DISCOVERY COMPLETE ===\n"
            f"Queries executed: {len(queries_processed)}\n"
            f"Keywords searched: {len(keyword_stats)}\n"
            f"New videos: {videos_discovered}\n"
            f"Rediscovered (virality tracking): {videos_rediscovered}\n"
            f"Skipped (already scanned): {videos_skipped}\n"
            f"Quota used: {quota_used}/{max_quota} ({quota_used/max_quota*100:.1f}%)\n"
            f"Efficiency: {efficiency:.2f} videos/unit\n"
            f"Duration: {duration:.1f}s"
        )

        self._save_metrics(stats)
        return stats

    def _process_results(self, results: list[dict]) -> tuple[int, int, int]:
        """
        Process search results with smart deduplication.

        Logic:
        - NEW video → Save + publish → count as discovered
        - EXISTS + not scanned → Update views, republish if trending → count as rediscovered
        - EXISTS + scanned → Skip completely → count as skipped

        Args:
            results: Raw YouTube API results

        Returns:
            (new_count, rediscovered_count, skipped_count)
        """
        new_count = 0
        rediscovered_count = 0
        skipped_count = 0

        logger.info(f"🎬 Processing {len(results)} videos...")

        for idx, video_data in enumerate(results, 1):
            try:
                # Extract metadata
                metadata = self.processor.extract_metadata(video_data)

                # Check if exists
                doc_ref = self.processor.firestore.collection("videos").document(
                    metadata.video_id
                )
                doc = doc_ref.get()

                if not doc.exists:
                    # BRAND NEW VIDEO
                    logger.debug(f"  [{idx}/{len(results)}] 🆕 NEW video: {metadata.video_id}")

                    # Match IPs (but save ALL videos regardless)
                    matched_ips = self.processor.match_ips(metadata)
                    metadata.matched_ips = matched_ips

                    if matched_ips:
                        logger.debug(f"      ✅ IP match: {matched_ips}")
                    else:
                        logger.debug(f"      ℹ️  No IP match (saving anyway)")

                    # Calculate initial risk
                    metadata.initial_risk = self.processor.calculate_initial_risk(
                        metadata, channel_risk=0
                    )
                    metadata.current_risk = metadata.initial_risk
                    metadata.risk_tier = self.processor.calculate_risk_tier(
                        metadata.initial_risk
                    )

                    # Save and publish ALL videos
                    if self.processor.save_and_publish(metadata):
                        new_count += 1
                        ip_info = f" IP:{matched_ips}" if matched_ips else " (no IP)"
                        logger.info(f"      ✅ NEW: {metadata.video_id} - '{metadata.title}' (risk={metadata.initial_risk}{ip_info})")
                    continue

                # VIDEO EXISTS - check if this config should subscribe to it
                old_data = doc.to_dict()
                vision_scan_status = old_data.get("vision_scan_status")
                old_matched_ips = old_data.get("matched_ips", [])

                logger.debug(f"  [{idx}/{len(results)}] 🔄 EXISTS: {metadata.video_id}, scan_status={vision_scan_status}")

                # Check if THIS config's IPs match the video
                new_matched_ips = self.processor.match_ips(metadata)

                # Find IPs that aren't already subscribed
                new_ips_to_add = [ip for ip in new_matched_ips if ip not in old_matched_ips]

                if new_ips_to_add:
                    # This config found the video but it's not subscribed yet!
                    logger.info(f"      🔔 SUBSCRIBING {len(new_ips_to_add)} new IPs to existing video: {metadata.video_id}")

                    # Add new IPs to matched_ips array
                    updated_ips = old_matched_ips + new_ips_to_add

                    # If video was already scanned, reset scan status so it gets rescanned!
                    update_data = {
                        "matched_ips": updated_ips,
                        "updated_at": datetime.now(timezone.utc),
                    }

                    if vision_scan_status == "scanned":
                        # Reset scan status - new config needs vision analysis!
                        update_data["vision_scan_status"] = None
                        logger.info(f"      🔄 RESETTING scan status - will be rescanned with new IPs!")

                    doc_ref.update(update_data)

                    # Republish so risk-analyzer can rescore with new IPs
                    metadata.matched_ips = updated_ips
                    message_data = metadata.model_dump_json().encode("utf-8")
                    self.processor.publisher.publish(self.processor.topic_path, message_data)

                    new_count += 1  # Count as NEW for this config!
                    logger.info(f"      ✅ NEW for this config: {metadata.video_id} - '{metadata.title}' (added IPs: {new_ips_to_add})")
                    continue

                if vision_scan_status == "scanned":
                    # Already scanned with vision analyzer and this config already subscribed - skip
                    skipped_count += 1
                    logger.debug(f"      ⏭️  SKIP: {metadata.video_id} (already scanned & subscribed)")
                    continue

                # EXISTS but NOT SCANNED - update for virality detection
                old_views = old_data.get("view_count", 0)
                new_views = metadata.view_count

                # Calculate view velocity
                updated_at = old_data.get("updated_at")
                if isinstance(updated_at, datetime):
                    time_elapsed_hours = (
                        datetime.now(timezone.utc) - updated_at
                    ).total_seconds() / 3600
                else:
                    time_elapsed_hours = 24  # Default to 24h if missing

                views_gained = new_views - old_views
                view_velocity = (
                    int(views_gained / time_elapsed_hours)
                    if time_elapsed_hours > 0
                    else 0
                )

                # Update metadata
                doc_ref.update({
                    "view_count": new_views,
                    "like_count": metadata.like_count,
                    "comment_count": metadata.comment_count,
                    "view_velocity": view_velocity,
                    "updated_at": datetime.now(timezone.utc),
                    "last_seen_at": datetime.now(timezone.utc),
                })

                # Check if trending (significant view increase)
                view_change_pct = (views_gained / old_views * 100) if old_views > 0 else 0
                is_trending = views_gained > 1000 or view_change_pct > 10

                if is_trending:
                    # Republish for priority rescore
                    message_data = metadata.model_dump_json().encode("utf-8")
                    self.processor.publisher.publish(
                        self.processor.topic_path, message_data
                    )
                    rediscovered_count += 1
                    logger.info(
                        f"      📈 TRENDING (republished): {metadata.video_id} - "
                        f"views {old_views:,} → {new_views:,} "
                        f"(+{views_gained:,}, +{view_change_pct:.1f}%, velocity={view_velocity}/hr)"
                    )
                else:
                    # Just update, don't republish
                    rediscovered_count += 1
                    logger.debug(
                        f"      ↻ UPDATE (no republish): {metadata.video_id} - "
                        f"views {old_views:,} → {new_views:,} (+{views_gained:,}, +{view_change_pct:.1f}%)"
                    )

            except Exception as e:
                logger.error(f"Error processing video: {e}", exc_info=True)
                continue

        return new_count, rediscovered_count, skipped_count

    def _save_metrics(self, stats: DiscoveryStats):
        """Save discovery metrics to Firestore."""
        try:
            self.processor.firestore.collection("discovery_metrics").add({
                "timestamp": stats.timestamp,
                "videos_discovered": stats.videos_discovered,
                "quota_used": stats.quota_used,
                "duration_seconds": stats.duration_seconds,
                "efficiency": (
                    stats.videos_discovered / stats.quota_used
                    if stats.quota_used > 0
                    else 0
                ),
            })
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _get_last_search_timestamps(self, keywords: list[str]) -> dict[str, datetime]:
        """
        Get last search timestamp for each keyword.

        Args:
            keywords: List of keywords to check

        Returns:
            Dict mapping keyword → last search datetime (only includes keywords that were searched before)
        """
        try:
            # Get all keyword searches for these keywords
            all_searches = (
                self.processor.firestore.collection("keyword_searches")
                .order_by("searched_at", direction="DESCENDING")
                .stream()
            )

            last_timestamps = {}
            seen_keywords = set()

            for doc in all_searches:
                data = doc.to_dict()
                keyword = data.get("keyword")

                # Only track keywords we're interested in
                if keyword not in keywords:
                    continue

                # Only keep latest search per keyword
                if keyword in seen_keywords:
                    continue
                seen_keywords.add(keyword)

                # Get last search timestamp
                searched_at = data.get("searched_at")
                if searched_at:
                    last_timestamps[keyword] = searched_at
                    logger.info(
                        f"  🕒 '{keyword}': Last searched {searched_at.strftime('%Y-%m-%d %H:%M')} "
                        f"({(datetime.now(timezone.utc) - searched_at).days}d ago)"
                    )

            # Log keywords that were never searched
            never_searched = set(keywords) - seen_keywords
            if never_searched:
                logger.info(f"  🆕 {len(never_searched)} keywords never searched: {list(never_searched)[:3]}...")

            return last_timestamps

        except Exception as e:
            logger.error(f"Failed to get last search timestamps: {e}", exc_info=True)
            return {}

    def _get_keywords_searched_today(self, today: str) -> tuple[set[str], dict[str, int]]:
        """
        Get list of keywords in cooldown (based on tier).

        Returns:
            (keywords_in_cooldown, cooldown_info)
            - keywords_in_cooldown: set of keywords still in cooldown
            - cooldown_info: dict mapping keyword → days_until_ready (for cycling)
        """
        try:
            from datetime import timedelta

            # Get all keyword searches, find latest per keyword
            all_searches = (
                self.processor.firestore.collection("keyword_searches")
                .order_by("searched_at", direction="DESCENDING")
                .stream()
            )

            keywords_in_cooldown = set()
            cooldown_info = {}  # keyword → days_until_ready
            seen_keywords = set()

            for doc in all_searches:
                data = doc.to_dict()
                keyword = data["keyword"]

                # Only check latest search per keyword
                if keyword in seen_keywords:
                    continue
                seen_keywords.add(keyword)

                # Check if still in cooldown
                searched_at = data.get("searched_at")
                cooldown_days = data.get("cooldown_days", 1)

                if searched_at:
                    days_since = (datetime.now(timezone.utc) - searched_at).days
                    days_until_ready = max(0, cooldown_days - days_since)

                    if days_since < cooldown_days:
                        keywords_in_cooldown.add(keyword)
                        cooldown_info[keyword] = days_until_ready
                        logger.debug(
                            f"  ⏸️  '{keyword}' in cooldown: {data.get('tier', 'UNKNOWN')} "
                            f"(searched {days_since}d ago, ready in {days_until_ready}d)"
                        )

            return keywords_in_cooldown, cooldown_info
        except Exception as e:
            logger.error(f"Failed to get keywords in cooldown: {e}")
            return set(), {}

    def _save_keyword_search(
        self,
        keyword: str,
        search_date: str,
        new_videos: int,
        rediscovered: int,
        skipped: int,
    ):
        """Save keyword search to Firestore for tracking and tier calculation."""
        try:
            total_results = new_videos + rediscovered + skipped
            efficiency = (new_videos / total_results * 100) if total_results > 0 else 0

            # Calculate tier based on efficiency (matching config tier system: 1, 2, 3)
            if efficiency >= 70:
                tier = "1"  # Tier 1: Search daily (best performance)
                cooldown_days = 1
            elif efficiency >= 40:
                tier = "2"  # Tier 2: Search every 3 days
                cooldown_days = 3
            else:
                tier = "3"  # Tier 3: Search weekly
                cooldown_days = 7

            self.processor.firestore.collection("keyword_searches").add({
                "keyword": keyword,
                "search_date": search_date,
                "searched_at": datetime.now(timezone.utc),
                "new_videos": new_videos,
                "rediscovered_videos": rediscovered,
                "skipped_videos": skipped,
                "total_results": total_results,
                "efficiency_pct": round(efficiency, 1),
                "tier": tier,
                "cooldown_days": cooldown_days,
            })
            logger.info(f"💎 {tier} keyword: '{keyword}' ({efficiency:.1f}% efficiency, cooldown={cooldown_days}d)")
        except Exception as e:
            logger.error(f"Failed to save keyword search: {e}")

    def _save_channel_scan(self, channel_id: str):
        """Save channel scan to Firestore to track when it was last scanned."""
        try:
            from google.cloud.firestore_v1 import Increment

            # Use channel_id as document ID to ensure we only have one record per channel
            doc_ref = self.processor.firestore.collection("channel_scans").document(channel_id)
            doc_ref.set({
                "channel_id": channel_id,
                "last_scanned_at": datetime.now(timezone.utc),
                "scan_count": Increment(1),  # Increment scan count
            }, merge=True)
            logger.debug(f"📺 Saved channel scan: {channel_id}")
        except Exception as e:
            logger.error(f"Failed to save channel scan: {e}")
