import { api } from './client'
import type { ChannelListResponse, ChannelProfile, ChannelStats, ChannelTier } from '../types'

export interface ChannelListParams {
  min_risk?: number
  tier?: ChannelTier
  action_status?: string
  sort_by?: string
  sort_desc?: boolean
  limit?: number
  offset?: number
}

export const channelsAPI = {
  list: (params?: ChannelListParams) => {
    const searchParams = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value))
        }
      })
    }
    const query = searchParams.toString()
    return api.get<ChannelListResponse>(`/channels${query ? `?${query}` : ''}`)
  },
  getStats: () => api.get<ChannelStats>('/channels/stats'),
  getChannel: (channelId: string) => api.get<ChannelProfile>(`/channels/${channelId}`),
}
