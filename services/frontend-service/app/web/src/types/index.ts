// Enums
export enum VideoStatus {
  DISCOVERED = 'discovered',
  PROCESSING = 'processing',
  ANALYZED = 'analyzed',
  FAILED = 'failed',
}

export enum ServiceStatus {
  HEALTHY = 'healthy',
  DEGRADED = 'degraded',
  UNHEALTHY = 'unhealthy',
  UNKNOWN = 'unknown',
}

export enum ChannelTier {
  CRITICAL = 'critical',
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low',
  MINIMAL = 'minimal',
}

// Vision Analysis types
export interface CharacterDetection {
  name: string
  screen_time_seconds: number
  prominence: 'primary' | 'secondary' | 'background'
  timestamps: string[]
  description: string
}

export interface IPAnalysisResult {
  ip_id: string
  ip_name: string
  contains_infringement: boolean
  characters_detected: CharacterDetection[]
  is_ai_generated: boolean
  ai_tools_detected: string[]
  fair_use_applies: boolean
  fair_use_reasoning: string
  content_type: string  // Accept any content type from backend
  infringement_likelihood: number
  reasoning: string
  recommended_action: string  // Accept any action from backend
}

export interface VisionAnalysis {
  ip_results: IPAnalysisResult[]
  overall_recommendation: string  // Accept any recommendation from backend
  overall_notes: string
}

// Video types
export interface VideoMetadata {
  video_id: string
  title: string
  channel_id: string
  channel_title: string
  published_at: string
  description?: string
  view_count: number
  like_count: number
  comment_count: number
  duration_seconds?: number
  tags: string[]
  category_id?: string
  thumbnail_url?: string
  matched_ips: string[]
  view_velocity?: number
  status: VideoStatus
  discovered_at: string
  updated_at?: string
  processing_started_at?: string  // When vision analysis started
  vision_analysis?: VisionAnalysis  // Added: Gemini analysis results
  last_analyzed_at?: string

  // Risk scoring fields
  scan_priority?: number  // Final scan priority (0-100)
  priority_tier?: string  // CRITICAL, HIGH, MEDIUM, LOW, VERY_LOW
  channel_risk?: number   // Channel risk component (0-100)
  video_risk?: number     // Video risk component (0-100)
}

export interface VideoListResponse {
  videos: VideoMetadata[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

// Channel types
export type ActionStatus = 'new' | 'in_review' | 'legal_action' | 'resolved' | 'monitoring'

export interface ChannelProfile {
  channel_id: string
  channel_title: string
  total_videos_found: number
  confirmed_infringements: number
  videos_cleared: number
  last_infringement_date?: string
  infringement_rate: number
  risk_score: number
  tier: ChannelTier
  is_newly_discovered: boolean
  last_scanned_at?: string
  next_scan_at?: string
  last_upload_date?: string
  posting_frequency_days?: number
  discovered_at: string
  subscriber_count?: number
  thumbnail_url?: string
  video_count?: number
  total_views?: number
  // Enforcement tracking
  action_status?: ActionStatus
  assigned_to?: string
  notes?: string
  last_action_date?: string
}

export interface ChannelListResponse {
  channels: ChannelProfile[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface ChannelStats {
  critical: number
  high: number
  medium: number
  low: number
  minimal: number
  total: number
}

// Discovery types
export interface DiscoveryStats {
  videos_discovered: number
  videos_with_ip_match: number
  videos_skipped_duplicate: number
  quota_used: number
  channels_tracked: number
  duration_seconds: number
  timestamp: string
}

export interface QuotaStatus {
  daily_quota: number
  used_quota: number
  remaining_quota: number
  utilization: number
  last_reset?: string
  next_reset?: string
}

export interface DiscoveryTriggerRequest {
  max_quota?: number
  priority?: string
}

export interface DiscoveryAnalytics {
  quota_stats: QuotaStatus
  discovery_stats: DiscoveryStats
  efficiency: number
  channel_count_by_tier: ChannelStats
}

// Status types
export interface ServiceHealth {
  service_name: string
  status: ServiceStatus
  last_check?: string
  url?: string
  error?: string
}

export interface LastDiscoveryRun {
  timestamp: string
  videos_discovered: number
  quota_used: number
  channels_tracked: number
  duration_seconds: number
  tier_breakdown: Record<string, unknown>
}

export interface SystemSummary {
  videos_discovered: number
  channels_tracked: number
  quota_used: number
  quota_total: number
  videos_analyzed: number
  infringements_found: number
  period_start: string
  period_end: string
  last_run?: LastDiscoveryRun
}

export interface SystemStatus {
  services: ServiceHealth[]
  summary: SystemSummary
  timestamp: string
}

// Keyword Performance types
export interface KeywordStat {
  keyword: string
  tier: '1' | '2' | '3'
  efficiency_pct: number
  new_videos: number
  total_results: number
  last_searched: string | null
  days_since_search: number
  cooldown_days: number
  in_cooldown: boolean
  days_until_ready: number
  search_date: string
}

export interface TierSummary {
  count: number
  avg_efficiency: number
  in_cooldown: number
  ready_to_search: number
}

export interface KeywordPerformance {
  keywords: KeywordStat[]
  by_tier: {
    '1': KeywordStat[]
    '2': KeywordStat[]
    '3': KeywordStat[]
  }
  tier_summary: Record<string, TierSummary>
  total_keywords: number
  timestamp: string
}
