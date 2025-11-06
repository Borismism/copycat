"""YouTube API client - simplified for single API key."""

import logging
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class YouTubeClient:
    """
    YouTube API client with single API key.

    Simple client for YouTube Data API v3.
    """

    def __init__(self, api_key: str):
        """Initialize YouTube client with single API key."""
        self.api_key = api_key

    def _build_youtube_service(self) -> Any:
        """Build YouTube API service."""
        return build("youtube", "v3", developerKey=self.api_key, cache_discovery=False)

    def search_videos(
        self,
        query: str | None = None,
        region_code: str = "US",
        max_results: int = 50,
        video_category_id: str | None = None,
        order: str = "relevance",
        published_after: str | None = None,
        published_before: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for videos on YouTube with PAGINATION for massive results.

        Args:
            query: Search query (optional)
            region_code: Region code for results
            max_results: Maximum number of results (1-1000) - uses pagination to get ALL results
            video_category_id: Filter by category (e.g., "20" for Gaming)
            order: Sort order (relevance, date, viewCount, rating)
            published_after: RFC 3339 timestamp - only videos after this date
            published_before: RFC 3339 timestamp - only videos before this date

        Returns:
            List of video data dictionaries (paginated up to max_results)
        """
        youtube = self._build_youtube_service()

        all_results = []
        next_page_token = None
        pages_fetched = 0
        max_pages = (max_results // 50) + (1 if max_results % 50 else 0)

        logger.info(f"Fetching up to {max_results} results ({max_pages} pages of 50)")
        if published_after:
            logger.info(f"Filtering videos published after: {published_after}")

        while len(all_results) < max_results and pages_fetched < max_pages:
            request_params = {
                "part": "id,snippet",
                "type": "video",
                "maxResults": min(50, max_results - len(all_results)),
                "regionCode": region_code,
                "order": order,
                "relevanceLanguage": "en",
            }

            if query:
                request_params["q"] = query

            if video_category_id:
                request_params["videoCategoryId"] = video_category_id

            if published_after:
                request_params["publishedAfter"] = published_after

            if published_before:
                request_params["publishedBefore"] = published_before

            if next_page_token:
                request_params["pageToken"] = next_page_token

            try:
                request = youtube.search().list(**request_params)
                response = request.execute()

                items = response.get("items", [])
                all_results.extend(items)
                pages_fetched += 1

                next_page_token = response.get("nextPageToken")

                logger.info(
                    f"Page {pages_fetched}/{max_pages}: Got {len(items)} videos (total: {len(all_results)})"
                )

                if not next_page_token:
                    logger.info(f"No more results available. Total: {len(all_results)}")
                    break

            except HttpError as e:
                logger.error(f"YouTube API error: {e}")
                raise

        logger.info(f"Pagination complete: {len(all_results)} total videos fetched")
        return all_results

    def get_trending_videos(
        self, region_code: str = "US", max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Get trending videos for a region."""
        youtube = self._build_youtube_service()

        try:
            request = youtube.videos().list(
                part="id,snippet,statistics,contentDetails",
                chart="mostPopular",
                regionCode=region_code,
                maxResults=min(max_results, 50),
            )
            response = request.execute()

            return response.get("items", [])

        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            raise

    def get_video_details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get detailed information for specific videos.

        Args:
            video_ids: List of video IDs (max 50 per request)

        Returns:
            List of video detail dictionaries
        """
        youtube = self._build_youtube_service()

        # Batch video IDs (max 50 per request)
        video_ids = video_ids[:50]

        try:
            request = youtube.videos().list(
                part="id,snippet,statistics,contentDetails",
                id=",".join(video_ids),
            )
            response = request.execute()

            return response.get("items", [])

        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            raise

    def get_channel_uploads(
        self, channel_id: str, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get recent uploads from a specific channel with pagination support.

        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of recent uploads (supports up to 500 with pagination)

        Returns:
            List of video data dictionaries
        """
        youtube = self._build_youtube_service()

        try:
            # Step 1: Get channel's uploads playlist ID
            request = youtube.channels().list(part="contentDetails", id=channel_id)
            response = request.execute()

            items = response.get("items", [])
            if not items:
                logger.warning(f"Channel {channel_id} not found")
                return []

            uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"][
                "uploads"
            ]

            # Step 2: Get videos from uploads playlist with pagination
            all_video_ids = []
            next_page_token = None
            pages_fetched = 0
            max_pages = (max_results // 50) + (1 if max_results % 50 else 0)

            while len(all_video_ids) < max_results and pages_fetched < max_pages:
                request_params = {
                    "part": "snippet,contentDetails",
                    "playlistId": uploads_playlist_id,
                    "maxResults": min(50, max_results - len(all_video_ids)),
                }

                if next_page_token:
                    request_params["pageToken"] = next_page_token

                request = youtube.playlistItems().list(**request_params)
                response = request.execute()

                # Extract video IDs
                video_ids = [
                    item["contentDetails"]["videoId"] for item in response.get("items", [])
                ]
                all_video_ids.extend(video_ids)
                pages_fetched += 1

                next_page_token = response.get("nextPageToken")

                if not next_page_token:
                    break

            if not all_video_ids:
                return []

            # Step 3: Get full details for all videos (in batches of 50)
            all_videos = []
            for i in range(0, len(all_video_ids), 50):
                batch = all_video_ids[i:i+50]
                videos = self.get_video_details(batch)
                all_videos.extend(videos)

            logger.info(f"Fetched {len(all_videos)} videos from channel {channel_id}")
            return all_videos

        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            raise

    def search_related_videos(
        self,
        video_metadata: dict[str, Any],
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Find videos similar to a viral video (VIRAL SNOWBALL STRATEGY - REDESIGNED).

        NOTE: YouTube DEPRECATED relatedToVideoId on Aug 7, 2023!
        New strategy: Search using video's tags + keywords from title

        Args:
            video_metadata: Full video metadata dict including tags, title, categoryId
            max_results: Maximum number of similar videos (default: 50)

        Returns:
            List of similar video data dictionaries

        Quota Cost:
            - 100 units for search
            - 1 unit for video.list
            - Total: 101 units for up to 50 videos

        Strategy:
            1. Extract tags from viral video
            2. Combine top 3 tags into search query
            3. Search by viewCount (find OTHER viral videos)
            4. Filter by same category for better relevance

        Example:
            Viral video: "Pikachu Spiderman AI Wedding" (20M views)
            Tags: ["Spiderman", "Pikachu", "AI", "shorts"]
            → Search: "Spiderman Pikachu AI" order=viewCount
            → Finds: 50 similar viral AI mashup videos
        """
        youtube = self._build_youtube_service()

        try:
            # Extract search terms from video metadata
            # YouTube API returns: {id, snippet: {title, tags, categoryId, ...}, ...}
            snippet = video_metadata.get("snippet", video_metadata)  # Fallback to root if already flattened

            tags = snippet.get("tags", [])
            title = snippet.get("title", "")
            category_id = snippet.get("categoryId", video_metadata.get("category_id"))

            logger.info(f"Video metadata - tags: {tags[:5] if tags else 'none'}, title: '{title[:60]}...'")

            # Build search query from tags (use top 3)
            if tags and len(tags) >= 2:
                # Use first 3 tags (usually most relevant)
                search_query = " ".join(tags[:3])
                logger.info(f"Using tags for query: {tags[:3]}")
            elif tags and len(tags) == 1:
                # Only 1 tag, add first 2 words from title
                title_words = title.split()[:2]
                search_query = f"{tags[0]} {' '.join(title_words)}"
                logger.info(f"Using 1 tag + title words: {tags[0]} + {title_words}")
            else:
                # Fallback: extract meaningful words from title
                # Remove hashtags, special chars, and short words
                import re
                # Remove hashtags and split by |, -, etc
                clean_title = re.sub(r'#\w+', '', title)  # Remove #hashtags
                clean_title = re.sub(r'[|]', ' ', clean_title)  # Replace | with space
                words = [w.strip() for w in clean_title.split() if len(w.strip()) > 2][:5]
                search_query = " ".join(words) if words else " ".join(title.split()[:3])
                logger.info(f"Using title words (no tags): {words[:5]}")

            # Clean up query
            search_query = search_query.strip()

            if not search_query:
                logger.warning(f"Could not build search query from video metadata: tags={tags}, title={title}")
                return []

            logger.info(f"Searching similar videos with query: '{search_query}'")

            # Search parameters
            search_params = {
                "part": "id,snippet",
                "q": search_query,
                "type": "video",
                "order": "viewCount",  # Find viral videos
                "maxResults": min(max_results, 50),
            }

            # Add category filter if available (improves relevance)
            if category_id:
                search_params["videoCategoryId"] = category_id

            request = youtube.search().list(**search_params)
            response = request.execute()

            items = response.get("items", [])

            if not items:
                logger.info(f"No similar videos found for query: {search_query}")
                return []

            # Extract video IDs
            video_ids = []
            for item in items:
                vid_id = item.get("id")
                if isinstance(vid_id, dict):
                    vid_id = vid_id.get("videoId")
                if vid_id:
                    video_ids.append(vid_id)

            # Get full video details
            if video_ids:
                videos = self.get_video_details(video_ids)
                logger.info(
                    f"Found {len(videos)} similar videos using tags/keywords "
                    f"(quota: 101 units = {101/len(videos):.1f} units/video)"
                )
                return videos

            return []

        except HttpError as e:
            logger.error(f"YouTube API error searching similar videos: {e}")
            raise

    def get_channel_details(self, channel_id: str) -> dict[str, Any] | None:
        """
        Get detailed information about a channel.

        Args:
            channel_id: YouTube channel ID

        Returns:
            Channel details dictionary with thumbnail URLs, or None if not found

        Quota Cost: 1 unit
        """
        youtube = self._build_youtube_service()

        try:
            request = youtube.channels().list(
                part="snippet,statistics,brandingSettings",
                id=channel_id
            )
            response = request.execute()

            items = response.get("items", [])
            if not items:
                logger.warning(f"Channel {channel_id} not found")
                return None

            channel = items[0]

            # Extract thumbnail URLs (multiple sizes available)
            thumbnails = channel.get("snippet", {}).get("thumbnails", {})

            result = {
                "channel_id": channel_id,
                "title": channel.get("snippet", {}).get("title", ""),
                "description": channel.get("snippet", {}).get("description", ""),
                "custom_url": channel.get("snippet", {}).get("customUrl", ""),
                "published_at": channel.get("snippet", {}).get("publishedAt", ""),
                "thumbnail_default": thumbnails.get("default", {}).get("url", ""),
                "thumbnail_medium": thumbnails.get("medium", {}).get("url", ""),
                "thumbnail_high": thumbnails.get("high", {}).get("url", ""),
                "subscriber_count": int(channel.get("statistics", {}).get("subscriberCount", 0)),
                "video_count": int(channel.get("statistics", {}).get("videoCount", 0)),
                "view_count": int(channel.get("statistics", {}).get("viewCount", 0)),
            }

            logger.info(f"Fetched channel details: {result['title']} ({result['subscriber_count']} subscribers)")
            return result

        except HttpError as e:
            logger.error(f"YouTube API error fetching channel details: {e}")
            return None

    def search_channel_videos(
        self,
        channel_id: str,
        keywords: list[str],
        max_results: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Deep scan: Search for videos within a specific channel matching keywords.

        Uses YouTube search API to find ALL videos in a channel matching our IP keywords.
        This is the most efficient way to find relevant content in channel history.

        Args:
            channel_id: YouTube channel ID to search within
            keywords: List of keywords to search for (OR logic)
            max_results: Maximum videos to return (default: 500)

        Returns:
            List of unique video data dictionaries matching any keyword

        Quota Cost:
            - 100 units per search query
            - 1 unit per video.list batch (50 videos)
            - Total: (len(keywords) * 100) + (total_videos / 50)
        """
        youtube = self._build_youtube_service()

        all_video_ids = set()  # Use set to deduplicate

        logger.info(f"Deep scanning channel {channel_id} for {len(keywords)} keywords")

        # Search for each keyword within the channel
        for keyword in keywords:
            try:
                next_page_token = None
                pages_fetched = 0
                max_pages = (max_results // 50) + (1 if max_results % 50 else 0)

                while pages_fetched < max_pages:
                    request_params = {
                        "part": "id,snippet",
                        "type": "video",
                        "channelId": channel_id,
                        "q": keyword,
                        "maxResults": 50,
                        "order": "date",  # Get all matches, newest first
                    }

                    if next_page_token:
                        request_params["pageToken"] = next_page_token

                    request = youtube.search().list(**request_params)
                    response = request.execute()

                    items = response.get("items", [])

                    # Extract video IDs
                    for item in items:
                        video_id = item.get("id")
                        if isinstance(video_id, dict):
                            video_id = video_id.get("videoId")
                        if video_id:
                            all_video_ids.add(video_id)

                    pages_fetched += 1
                    next_page_token = response.get("nextPageToken")

                    logger.info(
                        f"Keyword '{keyword}': page {pages_fetched}, found {len(items)} videos "
                        f"(total unique: {len(all_video_ids)})"
                    )

                    if not next_page_token or len(all_video_ids) >= max_results:
                        break

            except HttpError as e:
                logger.error(f"Error searching channel for keyword '{keyword}': {e}")
                continue

        if not all_video_ids:
            logger.info(f"No videos found in channel {channel_id} matching keywords")
            return []

        # Get full video details in batches of 50
        video_ids_list = list(all_video_ids)[:max_results]
        all_videos = []

        for i in range(0, len(video_ids_list), 50):
            batch = video_ids_list[i:i+50]
            try:
                videos = self.get_video_details(batch)
                all_videos.extend(videos)
            except HttpError as e:
                logger.error(f"Error fetching video details for batch: {e}")
                continue

        logger.info(
            f"Deep scan complete: {len(all_videos)} unique videos found in channel {channel_id}"
        )

        return all_videos
