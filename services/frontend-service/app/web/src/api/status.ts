import { api } from './client'
import type { ServiceHealth, SystemStatus, SystemSummary } from '../types'

export const statusAPI = {
  getServices: () => api.get<ServiceHealth[]>('/status/services'),
  getSummary: () => api.get<SystemSummary>('/status/summary'),
  getSystemStatus: () => api.get<SystemStatus>('/status'),
}
