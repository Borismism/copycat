# Copycat Discovery Service - Architecture Diagram

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        COPYCAT DISCOVERY SERVICE                              │
│                     Intelligent AI Copyright Detection                        │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│   YouTube Data API  │  ← External API (10,000 units/day quota)
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DISCOVERY ENGINE                                    │
│                        (160 LOC, 95% coverage)                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │  async discover() - Main Orchestrator                       │            │
│  │                                                              │            │
│  │  Phase 1: Channel Tracking (70% quota)                      │            │
│  │  ├─→ Get channels due for scan                              │            │
│  │  ├─→ Scan each channel (3 units)                            │            │
│  │  └─→ Update channel tier                                    │            │
│  │                                                              │            │
│  │  Phase 2: Trending Videos (20% quota)                       │            │
│  │  ├─→ Get trending videos (1 unit/50 videos)                 │            │
│  │  └─→ Process high-volume cheap discovery                    │            │
│  │                                                              │            │
│  │  Phase 3: Targeted Keywords (10% quota)                     │            │
│  │  ├─→ Get priority keywords                                  │            │
│  │  ├─→ Search each keyword (100 units)                        │            │
│  │  └─→ High-precision expensive discovery                     │            │
│  └─────────────────────────────────────────────────────────────┘            │
└────────┬──────────────┬──────────────┬──────────────┬───────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
   ┌─────────┐    ┌──────────┐  ┌──────────┐   ┌──────────────┐
   │ YouTube │    │  Video   │  │ Channel  │   │    Quota     │
   │ Client  │    │Processor │  │ Tracker  │   │   Manager    │
   └─────────┘    └──────────┘  └──────────┘   └──────────────┘
```

## Component Interactions

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       VIDEO PROCESSING PIPELINE                            │
└───────────────────────────────────────────────────────────────────────────┘

   YouTube API Response
           │
           ▼
   ┌───────────────┐
   │ YouTubeClient │  ← Fetch video data, channel info, trending
   └───────┬───────┘
           │ Raw API data
           ▼
   ┌───────────────────────────────────────────────────────┐
   │           VIDEO PROCESSOR (116 LOC, 100%)              │
   │                                                         │
   │  1. extract_metadata()                                 │
   │     └─→ Parse YouTube API response to VideoMetadata    │
   │                                                         │
   │  2. is_duplicate()                                     │
   │     └─→ Check Firestore (30-day lookback)             │
   │                                                         │
   │  3. match_ips()                                        │
   │     └─→ Match against IP targets (Justice League)     │
   │                                                         │
   │  4. save_and_publish()                                 │
   │     ├─→ Save to Firestore                              │
   │     └─→ Publish to PubSub                              │
   └─────────────┬─────────────────────────────────────────┘
                 │
                 ├─→ Firestore: videos collection
                 │   (video_id, title, channel_id, matched_ips, ...)
                 │
                 └─→ PubSub: discovered-videos topic
                     (triggers risk-scorer-service)


┌───────────────────────────────────────────────────────────────────────────┐
│                      CHANNEL INTELLIGENCE SYSTEM                           │
└───────────────────────────────────────────────────────────────────────────┘

   ┌────────────────────────────────────────────┐
   │  CHANNEL TRACKER (150 LOC, 86% coverage)   │
   │                                            │
   │  ┌──────────────────────────────────────┐ │
   │  │  Channel Tier Calculation            │ │
   │  │                                      │ │
   │  │  PLATINUM: >50% infringement        │ │
   │  │  GOLD:     25-50% infringement      │ │
   │  │  SILVER:   10-25% infringement      │ │
   │  │  BRONZE:   <10% infringement        │ │
   │  │  IGNORE:   0% after 20+ videos      │ │
   │  └──────────────────────────────────────┘ │
   │                                            │
   │  ┌──────────────────────────────────────┐ │
   │  │  Scan Frequency                      │ │
   │  │                                      │ │
   │  │  PLATINUM: Every 24 hours           │ │
   │  │  GOLD:     Every 72 hours           │ │
   │  │  SILVER:   Every 7 days             │ │
   │  │  BRONZE:   Every 30 days            │ │
   │  │  IGNORE:   Never                    │ │
   │  └──────────────────────────────────────┘ │
   └───────────────────┬────────────────────────┘
                       │
                       ▼
   ┌────────────────────────────────────────────┐
   │  Firestore: channels collection            │
   │                                            │
   │  channel_id: UC_xxxxx                     │
   │  channel_title: "AI Movies Daily"         │
   │  tier: "platinum"                          │
   │  total_videos_found: 156                   │
   │  infringing_videos_count: 136              │
   │  infringement_rate: 0.87                   │
   │  last_scanned_at: 2025-10-27T10:00:00Z    │
   │  next_scan_at: 2025-10-28T10:00:00Z       │
   └────────────────────────────────────────────┘


┌───────────────────────────────────────────────────────────────────────────┐
│                        QUOTA MANAGEMENT SYSTEM                             │
└───────────────────────────────────────────────────────────────────────────┘

   ┌────────────────────────────────────────────┐
   │   QUOTA MANAGER (72 LOC, 93% coverage)    │
   │                                            │
   │  Daily Quota: 10,000 units                │
   │                                            │
   │  ┌──────────────────────────────────────┐ │
   │  │  Operation Costs                     │ │
   │  │                                      │ │
   │  │  search:           100 units         │ │
   │  │  video_details:    1 unit            │ │
   │  │  trending:         1 unit            │ │
   │  │  channel_details:  3 units           │ │
   │  └──────────────────────────────────────┘ │
   │                                            │
   │  ┌──────────────────────────────────────┐ │
   │  │  Smart Allocation                    │ │
   │  │                                      │ │
   │  │  Channel tracking: 7,000 (70%)      │ │
   │  │  Trending:         2,000 (20%)      │ │
   │  │  Keywords:         1,000 (10%)      │ │
   │  └──────────────────────────────────────┘ │
   └───────────────────┬────────────────────────┘
                       │
                       ▼
   ┌────────────────────────────────────────────┐
   │  Firestore: quota_usage collection         │
   │                                            │
   │  date: "2025-10-28"                       │
   │  used: 8,234                               │
   │  by_operation: {                           │
   │    "channel_tracking": 5,500               │
   │    "trending": 1,234                       │
   │    "keyword_search": 1,500                 │
   │  }                                         │
   └────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DISCOVERY DATA FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

[1] Trigger: Cloud Scheduler / API Call / Manual
         │
         ▼
[2] DiscoveryEngine.discover()
         │
         ├──[3a] Phase 1: Channel Tracking (70% quota)
         │        │
         │        ├─→ ChannelTracker.get_channels_due_for_scan()
         │        │   └─→ Firestore: channels WHERE next_scan_at <= NOW()
         │        │
         │        ├─→ YouTubeClient.get_channel_uploads(channel_id)
         │        │   └─→ YouTube API: 3 units per channel
         │        │
         │        ├─→ VideoProcessor.process_batch(videos)
         │        │   ├─→ Extract metadata
         │        │   ├─→ Check duplicates (Firestore)
         │        │   ├─→ Match IPs (Justice League characters)
         │        │   ├─→ Save to Firestore
         │        │   └─→ Publish to PubSub
         │        │
         │        └─→ ChannelTracker.update_after_scan()
         │            └─→ Recalculate tier, set next_scan_at
         │
         ├──[3b] Phase 2: Trending (20% quota)
         │        │
         │        ├─→ YouTubeClient.get_trending_videos()
         │        │   └─→ YouTube API: 1 unit for 50 videos
         │        │
         │        └─→ VideoProcessor.process_batch(videos)
         │
         └──[3c] Phase 3: Keywords (10% quota)
                  │
                  ├─→ Get priority keywords from IP targets
                  │
                  ├─→ YouTubeClient.search_videos(keyword)
                  │   └─→ YouTube API: 100 units per search
                  │
                  └─→ VideoProcessor.process_batch(videos)

[4] Results stored in:
         │
         ├─→ Firestore: videos collection
         │   └─→ {video_id, title, channel_id, matched_ips, view_count, ...}
         │
         ├─→ Firestore: channels collection
         │   └─→ {channel_id, tier, infringement_rate, next_scan_at, ...}
         │
         └─→ PubSub: discovered-videos topic
             └─→ Triggers risk-scorer-service

[5] Monitoring:
         │
         ├─→ QuotaManager tracks usage
         │   └─→ Firestore: quota_usage collection
         │
         └─→ DiscoveryStats returned
             └─→ {videos_discovered, quota_used, channels_tracked, ...}
```

## API Endpoints Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DISCOVERY SERVICE API                                  │
│                       Port 8080 (local) / Cloud Run (prod)                  │
└─────────────────────────────────────────────────────────────────────────────┘

GET /health
    └─→ Health check endpoint
        Returns: {status: "healthy", service: "discovery-service"}

POST /discover
    ├─→ Triggers intelligent discovery
    │   Query params: max_quota (optional)
    └─→ Returns: DiscoveryStats
        {
          videos_discovered: 1,234,
          videos_with_ip_match: 892,
          videos_skipped_duplicate: 342,
          quota_used: 8,456,
          channels_tracked: 2,150,
          duration_seconds: 145.3,
          timestamp: "2025-10-28T10:30:00Z"
        }

GET /discover/channels
    ├─→ List tracked channels
    │   Query params: tier (optional), limit (default: 50)
    └─→ Returns: list[ChannelProfile]
        [{
          channel_id: "UC_xxxxx",
          channel_title: "AI Movies Daily",
          tier: "platinum",
          infringement_rate: 0.87,
          total_videos_found: 156,
          infringing_videos_count: 136,
          last_scanned_at: "2025-10-27T10:00:00Z",
          next_scan_at: "2025-10-28T10:00:00Z"
        }]

GET /discover/analytics/discovery
    ├─→ Discovery performance metrics
    └─→ Returns: {
          quota: {
            total_quota: 10_000,
            used_quota: 8,234,
            remaining_quota: 1,766,
            utilization: 82.34%
          },
          channels: {
            total: 1,247,
            by_tier: {
              platinum: 12,
              gold: 45,
              silver: 234,
              bronze: 789,
              ignore: 167
            }
          }
        }

GET /discover/quota
    ├─→ Current quota status
    └─→ Returns: {
          daily_quota: 10_000,
          used: 8,234,
          remaining: 1,766,
          utilization_percent: 82.34,
          timestamp: "2025-10-28T10:30:00Z"
        }

GET /docs
    └─→ Swagger UI / OpenAPI documentation
```

## Firestore Collections Schema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FIRESTORE COLLECTIONS                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Collection: videos
Document ID: {video_id}
{
  video_id: "dQw4w9WgXcQ",
  title: "AI Generated Superman Movie",
  channel_id: "UC_xxxxx",
  channel_title: "AI Movies Daily",
  published_at: Timestamp,
  description: "...",
  view_count: 125_000,
  like_count: 5_200,
  comment_count: 890,
  duration_seconds: 600,
  tags: ["Superman", "AI", "Sora"],
  matched_ips: ["Superman", "Justice League"],
  view_velocity: 1_250.5,  // views per hour
  discovered_at: Timestamp,
  updated_at: Timestamp,
  status: "discovered"
}

Collection: channels
Document ID: {channel_id}
{
  channel_id: "UC_xxxxx",
  channel_title: "AI Movies Daily",
  tier: "platinum",  // platinum, gold, silver, bronze, ignore
  subscriber_count: 245_000,
  total_videos_found: 156,
  infringing_videos_count: 136,
  infringement_rate: 0.8717,  // 87.17%
  last_scanned_at: Timestamp,
  next_scan_at: Timestamp,
  avg_views_per_video: 85_000,
  posting_frequency_days: 2.5,
  discovered_at: Timestamp
}

Collection: quota_usage
Document ID: {date} (e.g., "2025-10-28")
{
  date: "2025-10-28",
  total_quota: 10_000,
  used_quota: 8,234,
  remaining_quota: 1,766,
  by_operation: {
    channel_tracking: 5,500,
    trending: 1,234,
    keyword_search: 1,500
  },
  by_hour: {
    "00": 234,
    "01": 456,
    ...
    "23": 123
  },
  timestamp: Timestamp
}

Collection: view_snapshots
Document ID: {video_id}_{timestamp}
{
  video_id: "dQw4w9WgXcQ",
  view_count: 125_000,
  timestamp: Timestamp,
  hours_since_published: 48.5
}
```

## Performance Metrics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       EFFICIENCY COMPARISON                                  │
└─────────────────────────────────────────────────────────────────────────────┘

BEFORE REDESIGN (Keyword-only strategy):
├─ Daily quota: 10,000 units
├─ Search cost: 100 units per 50 videos
├─ Total searches: 100 searches/day
├─ Videos checked: 5,000 videos/day
├─ Success rate: ~20% (keyword spam)
└─ Videos discovered: ~1,000 videos/day

AFTER REDESIGN (Channel-first strategy):
├─ Daily quota: 10,000 units
├─ Allocation:
│  ├─ Channel tracking: 7,000 units (70%)
│  │  ├─ Cost: 3 units per channel
│  │  ├─ Channels scanned: 2,333 channels/day
│  │  ├─ Videos checked: ~40,000 videos/day
│  │  └─ Success rate: ~70% (smart targeting)
│  ├─ Trending: 2,000 units (20%)
│  │  ├─ Cost: 1 unit per 50 videos
│  │  ├─ Videos checked: ~100,000 videos/day
│  │  └─ Success rate: ~5% (broad net)
│  └─ Keywords: 1,000 units (10%)
│     ├─ Cost: 100 units per 50 videos
│     ├─ Videos checked: ~500 videos/day
│     └─ Success rate: ~20% (targeted)
└─ Videos discovered: ~27,776 videos/day

IMPROVEMENT: 27.8x more videos discovered per day
```

---

**Generated:** 2025-10-28
**Epic:** 4 - Cleanup & Documentation
**Status:** Complete
