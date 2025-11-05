import { api } from './client'

export interface VisionBudgetStats {
  daily_budget_eur: number
  daily_budget_usd: number
  budget_used_eur: number
  budget_used_usd: number
  budget_remaining_eur: number
  budget_remaining_usd: number
  utilization_percentage: number
  total_requests: number
  total_input_tokens: number
  total_output_tokens: number
  estimated_cost_usd: number
  cache_age_seconds: number
  data_from_project: string
  last_updated: string
}

export interface GeminiConfiguration {
  model_name: string
  model_version: string
  region: string
  input_method: string
  resolution: string
  tokens_per_frame: number
  rate_limit_type: string
  max_output_tokens: number
  input_cost_per_1m_tokens: number
  output_cost_per_1m_tokens: number
  audio_cost_per_1m_tokens: number
}

export interface BatchScanResponse {
  success: boolean
  message: string
  videos_queued: number
  estimated_cost_usd?: number
  budget_remaining_usd?: number
}

export interface VisionAnalytics {
  total_analyzed: number
  total_errors: number
  success_rate: number
  infringements_found: number
  detection_rate: number
  avg_processing_time_seconds: number
  total_cost_usd: number
  videos_pending: number
  last_24h: {
    analyzed: number
    errors: number
    cost_usd: number
  }
  by_status: {
    success: number
    error: number
    pending: number
    processing: number
  }
  recent_errors: Array<{
    video_id: string
    error_message: string
    timestamp: string
  }>
}

export const visionAPI = {
  getBudgetStats: () => api.get<VisionBudgetStats>('/vision/budget'),
  getConfiguration: () => api.get<GeminiConfiguration>('/vision/config'),
  updateConfiguration: (config: GeminiConfiguration) => api.put<GeminiConfiguration>('/vision/config', config),
  getAnalytics: () => api.get<VisionAnalytics>('/vision/analytics'),
  // Call vision-analyzer-service directly (port 8083) for batch scan
  startBatchScan: async (batch_size: number) => {
    const response = await fetch('http://localhost:8083/admin/batch-scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: batch_size, min_priority: 0, force: false })
    })
    if (!response.ok) {
      throw new Error(`Batch scan failed: ${response.statusText}`)
    }
    return response.json()
  },
}
