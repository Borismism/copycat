import { memo, useMemo } from 'react'
import type { ChannelProfile, ChannelTier, ActionStatus } from '../types'

interface ChannelCardProps {
  channel: ChannelProfile
  isScanning: boolean
  canStartScans: boolean
  userRole: string
  onSelect: (channel: ChannelProfile) => void
  onScanAllVideos: (channel: ChannelProfile) => void
  onDeepScan: (channel: ChannelProfile) => void
}

// Memoized helper functions
const getTierColor = (tier: ChannelTier): string => {
  switch (tier) {
    case 'critical': return 'bg-red-100 text-red-800 border-red-300'
    case 'high': return 'bg-orange-100 text-orange-800 border-orange-300'
    case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300'
    case 'low': return 'bg-green-100 text-green-800 border-green-300'
    case 'minimal': return 'bg-gray-100 text-gray-800 border-gray-300'
  }
}

const getActionStatusColor = (status?: ActionStatus): string => {
  if (!status) return 'bg-gray-100 text-gray-600 border-gray-300'
  switch (status) {
    case 'new': return 'bg-blue-100 text-blue-800 border-blue-300'
    case 'in_review': return 'bg-yellow-100 text-yellow-800 border-yellow-300'
    case 'legal_action': return 'bg-red-100 text-red-800 border-red-300'
    case 'resolved': return 'bg-green-100 text-green-800 border-green-300'
    case 'monitoring': return 'bg-purple-100 text-purple-800 border-purple-300'
  }
}

const getActionStatusLabel = (status?: ActionStatus): string => {
  if (!status) return 'Not Reviewed'
  return status.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

/**
 * Memoized ChannelCard component - only re-renders when props change.
 * This prevents unnecessary re-renders when parent state changes (modals, filters, etc.)
 */
export const ChannelCard = memo(function ChannelCard({
  channel,
  isScanning,
  canStartScans,
  userRole,
  onSelect,
  onScanAllVideos,
  onDeepScan,
}: ChannelCardProps) {
  // Memoize expensive calculations
  const { videosScanned, infringementRate } = useMemo(() => {
    const scanned = channel.confirmed_infringements + channel.videos_cleared
    const rate = scanned > 0 ? (channel.confirmed_infringements / scanned) * 100 : 0
    return { videosScanned: scanned, infringementRate: rate }
  }, [channel.confirmed_infringements, channel.videos_cleared])

  const tierColorClass = useMemo(() => getTierColor(channel.tier), [channel.tier])
  const statusColorClass = useMemo(() => getActionStatusColor(channel.action_status), [channel.action_status])
  const statusLabel = useMemo(() => getActionStatusLabel(channel.action_status), [channel.action_status])

  const priorityBadge = useMemo(() => {
    if (channel.tier === 'critical' && channel.confirmed_infringements > 0 && channel.action_status !== 'resolved') {
      return (
        <span className="px-2 py-1 text-xs font-bold bg-red-600 text-white rounded-full animate-pulse">
          URGENT
        </span>
      )
    }
    if (channel.tier === 'high' && channel.confirmed_infringements > 0 && !channel.action_status) {
      return (
        <span className="px-2 py-1 text-xs font-bold bg-orange-500 text-white rounded-full">
          NEEDS REVIEW
        </span>
      )
    }
    return null
  }, [channel.tier, channel.confirmed_infringements, channel.action_status])

  const unscannedCount = channel.total_videos_found - videosScanned

  return (
    <div
      onClick={() => onSelect(channel)}
      className="bg-white rounded-lg shadow-lg border border-gray-200 hover:shadow-xl hover:scale-[1.02] transition-all overflow-hidden cursor-pointer"
    >
      {/* Header with centered thumbnail */}
      <div className="bg-gradient-to-br from-red-500 to-red-700 px-5 py-6 border-b border-red-800 relative">
        {/* Centered Avatar/Thumbnail */}
        <div className="flex justify-center mb-4">
          {channel.thumbnail_url ? (
            <img
              src={channel.thumbnail_url}
              alt={channel.channel_title}
              className="w-32 h-32 rounded-full object-cover shadow-2xl border-4 border-white"
              referrerPolicy="no-referrer"
              crossOrigin="anonymous"
              loading="lazy"
            />
          ) : (
            <div className="w-32 h-32 bg-white rounded-full flex items-center justify-center text-red-600 text-5xl font-bold shadow-2xl border-4 border-white">
              {channel.channel_title.charAt(0).toUpperCase()}
            </div>
          )}
        </div>

        {/* Channel Title - Centered */}
        <h3 className="text-lg font-bold text-white text-center truncate mb-3" title={channel.channel_title}>
          {channel.channel_title}
        </h3>

        {/* Badges - Centered */}
        <div className="flex items-center justify-center gap-2 flex-wrap">
          <span className={`px-2 py-1 text-xs font-bold rounded-full border bg-white ${tierColorClass}`}>
            {channel.tier.toUpperCase()}
          </span>
          <span className={`px-2 py-1 text-xs font-medium rounded-full border bg-white ${statusColorClass}`}>
            {statusLabel}
          </span>
        </div>

        {/* Priority Badge - Top Right */}
        <div className="absolute top-3 right-3">
          {priorityBadge}
        </div>
      </div>

      {/* Main Metrics - Compact List Format */}
      <div className="p-5">
        <div className="space-y-2 text-sm">
          {/* Risk Score */}
          <div className="flex justify-between items-center">
            <span className="text-gray-600 font-medium">Risk Score</span>
            <span className="text-xl font-bold text-gray-900">{channel.risk_score}/100</span>
          </div>

          {/* Infringements with Rate */}
          <div className="flex justify-between items-center">
            <span className="text-gray-600 font-medium">Infringements</span>
            <div className="text-right">
              <span className="text-xl font-bold text-red-600">{channel.confirmed_infringements}</span>
              <span className={`ml-2 text-sm font-medium ${
                infringementRate > 50 ? 'text-red-600' :
                infringementRate > 25 ? 'text-orange-600' :
                infringementRate > 0 ? 'text-yellow-600' :
                'text-green-600'
              }`}>
                {infringementRate.toFixed(1)}% rate
              </span>
            </div>
          </div>

          {/* Cleared */}
          <div className="flex justify-between items-center">
            <span className="text-gray-600 font-medium">Cleared</span>
            <span className="text-lg font-bold text-green-600">{channel.videos_cleared}</span>
          </div>

          {/* Total Found */}
          <div className="flex justify-between items-center">
            <span className="text-gray-600 font-medium">Total Found</span>
            <span className="text-lg font-bold text-gray-900">{channel.total_videos_found}</span>
          </div>

          {/* Unscanned */}
          <div className="flex justify-between items-center">
            <span className="text-gray-600 font-medium">Unscanned</span>
            <span className="text-lg font-bold text-orange-600">{unscannedCount}</span>
          </div>

          {/* Optional: Subscribers & Total Views (collapsed) */}
          <div className="pt-3 mt-3 border-t border-gray-200 text-xs text-gray-500 space-y-1">
            <div className="flex justify-between">
              <span>Subscribers:</span>
              <span className="font-medium">
                {channel.subscriber_count ? channel.subscriber_count.toLocaleString() : 'N/A'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Total Views:</span>
              <span className="font-medium">
                {channel.total_views ? channel.total_views.toLocaleString() : '0'}
              </span>
            </div>
            {channel.assigned_to && (
              <div className="flex justify-between">
                <span>Assigned:</span>
                <span className="font-medium truncate ml-2" title={channel.assigned_to}>{channel.assigned_to}</span>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-4 pt-3 border-t border-gray-200 flex gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onScanAllVideos(channel)
            }}
            className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isScanning || !canStartScans}
            title={!canStartScans ? `${userRole} role cannot start scans` : "Queue all unscanned videos for Gemini vision analysis (skips already analyzed videos)"}
          >
            Scan All Videos
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDeepScan(channel)
            }}
            className="flex-1 px-3 py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isScanning || !canStartScans}
            title={!canStartScans ? `${userRole} role cannot trigger discovery` : `Fetch the latest 50 videos from this YouTube channel${channel.video_count && channel.video_count >= 50 ? ' (channel has 50+ videos)' : ''}`}
          >
            Discover
          </button>
        </div>
      </div>
    </div>
  )
})

// Export helper functions for use in modals
export { getTierColor, getActionStatusColor, getActionStatusLabel }
