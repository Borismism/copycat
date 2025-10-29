import { api } from './client'
import type {
  DiscoveryStats,
  QuotaStatus,
  DiscoveryAnalytics,
  DiscoveryTriggerRequest,
} from '../types'

export const discoveryAPI = {
  trigger: (request: DiscoveryTriggerRequest) =>
    api.post<DiscoveryStats>('/discovery/trigger', request),
  getQuota: () => api.get<QuotaStatus>('/discovery/quota'),
  getAnalytics: () => api.get<DiscoveryAnalytics>('/discovery/analytics'),
}
