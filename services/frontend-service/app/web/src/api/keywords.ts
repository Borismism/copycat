const API_BASE = 'http://localhost:8080'

export interface KeywordScanStat {
  keyword: string
  priority: string
  last_scanned_at: string | null
  total_scans: number
  videos_found: number
  last_result_count: number
  ip_id: string | null
}

export interface KeywordStatsResponse {
  total_keywords: number
  scanned_keywords: number
  never_scanned_keywords: number
  keywords: KeywordScanStat[]
}

export interface LastRunKeyword {
  keyword: string
  priority: string
  videos_found: number
  scanned_at: string | null
}

export interface LastRunStatsResponse {
  scan_time: string | null
  keywords_scanned: number
  total_videos_found: number
  keywords: LastRunKeyword[]
}

export const keywordsAPI = {
  async getStats(): Promise<KeywordStatsResponse> {
    const response = await fetch(`${API_BASE}/api/keywords/stats`)
    if (!response.ok) throw new Error('Failed to fetch keyword stats')
    return response.json()
  },

  async getLastRunStats(): Promise<LastRunStatsResponse> {
    const response = await fetch(`${API_BASE}/api/keywords/stats/last-run`)
    if (!response.ok) throw new Error('Failed to fetch last run stats')
    return response.json()
  }
}
