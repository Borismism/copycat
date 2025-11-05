import { api } from './client'
import type {
  DiscoveryStats,
  QuotaStatus,
  DiscoveryAnalytics,
  DiscoveryTriggerRequest,
  KeywordPerformance,
} from '../types'

export const discoveryAPI = {
  trigger: (request: DiscoveryTriggerRequest) =>
    api.post<DiscoveryStats>('/discovery/trigger', request),
  getQuota: () => api.get<QuotaStatus>('/discovery/quota'),
  getAnalytics: () => api.get<DiscoveryAnalytics>('/discovery/analytics'),
  getKeywordPerformance: () => api.get<KeywordPerformance>('/discover/keywords/performance'),
}
