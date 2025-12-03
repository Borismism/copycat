import { useQuery } from '@tanstack/react-query'
import { channelsAPI, type ChannelListParams } from '../api/channels'

/**
 * Hook for fetching channel statistics.
 * Stats are cached for 60 seconds (matching backend cache TTL).
 * This is loaded ONCE and doesn't need to reload when filters change.
 */
export function useChannelStats() {
  return useQuery({
    queryKey: ['channelStats'],
    queryFn: () => channelsAPI.getStats(),
    staleTime: 60 * 1000, // 60 seconds - matches backend cache
    gcTime: 5 * 60 * 1000, // 5 minutes cache retention
  })
}

/**
 * Hook for fetching channel list with filters.
 * Automatically refetches when params change.
 * Results cached for 30 seconds.
 */
export function useChannelList(params: ChannelListParams) {
  return useQuery({
    queryKey: ['channels', params],
    queryFn: () => channelsAPI.list(params),
    staleTime: 30 * 1000, // 30 seconds
  })
}

/**
 * Hook for fetching a single channel by ID.
 */
export function useChannel(channelId: string | null) {
  return useQuery({
    queryKey: ['channel', channelId],
    queryFn: () => channelsAPI.getChannel(channelId!),
    enabled: !!channelId,
    staleTime: 30 * 1000,
  })
}
