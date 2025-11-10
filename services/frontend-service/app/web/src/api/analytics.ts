import { api } from './client'

export interface HourlyStats {
  timestamp: string
  discoveries: number
  analyses: number
  infringements: number
}

export interface DailyStats {
  timestamp: string
  discoveries: number
  analyses: number
  infringements: number
}

export interface Alert {
  id: string
  type: 'critical' | 'warning' | 'info'
  title: string
  message: string
  action: string | null
  timestamp: string
}

export interface SystemHealth {
  alerts: Alert[]
  warnings: Alert[]
  info: Alert[]
  timestamp: string
}

export interface PerformanceMetric {
  value: number
  target: number
  score: number
  status: string
}

export interface BudgetMetric {
  value: number
  spent: number
  total: number
  score: number
  status: string
}

export interface QueueMetric {
  pending: number
  threshold: number
  score: number
  status: string
}

export interface PerformanceMetrics {
  discovery_efficiency: PerformanceMetric
  analysis_throughput: PerformanceMetric
  budget_utilization: BudgetMetric
  queue_health: QueueMetric
}

export interface Event {
  id: string
  type: 'discovery' | 'infringement' | 'analysis' | 'channel'
  title: string
  message: string
  timestamp: string
  icon: string
  video_id?: string
}

export interface RecentEvents {
  events: Event[]
  total: number
}

export const analyticsAPI = {
  async getHourlyStats(hours: number = 24, startDate?: string): Promise<{ hours: HourlyStats[] }> {
    const params = new URLSearchParams({ hours: hours.toString() })
    if (startDate) {
      params.append('start_date', startDate)
    }
    return api.get(`/analytics/hourly-stats?${params}`)
  },

  async getDailyStats(days: number = 30, startDate?: string): Promise<{ days: DailyStats[] }> {
    const params = new URLSearchParams({ days: days.toString() })
    if (startDate) {
      params.append('start_date', startDate)
    }
    return api.get(`/analytics/daily-stats?${params}`)
  },

  async getSystemHealth(): Promise<SystemHealth> {
    return api.get('/analytics/system-health')
  },

  async getPerformanceMetrics(): Promise<PerformanceMetrics> {
    return api.get('/analytics/performance-metrics')
  },

  async getRecentEvents(limit: number = 20): Promise<RecentEvents> {
    return api.get(`/analytics/recent-events?limit=${limit}`)
  },

  async getOverview(): Promise<any> {
    return api.get('/analytics/overview')
  },
}
