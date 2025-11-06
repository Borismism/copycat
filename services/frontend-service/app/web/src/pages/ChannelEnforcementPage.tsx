import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { channelsAPI } from '../api/channels'
import type { ChannelProfile, ChannelStats, ChannelTier, ActionStatus } from '../types'
import { useAuth } from '../contexts/AuthContext'
import ScanProgressNotification from '../components/ScanProgressNotification'

type SortOption = {
  label: string
  field: string
  desc: boolean
}

const SORT_OPTIONS: SortOption[] = [
  { label: 'Highest Risk Score', field: 'risk_score', desc: true },
  { label: 'Most Infringements', field: 'confirmed_infringements', desc: true },
  { label: 'Most Videos Found', field: 'total_videos_found', desc: true },
  { label: 'Most Recently Scanned', field: 'last_scanned_at', desc: true },
  { label: 'Most Recently Discovered', field: 'discovered_at', desc: true },
]

export default function ChannelEnforcementPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [channels, setChannels] = useState<ChannelProfile[]>([])
  const [, setStats] = useState<ChannelStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [sortBy, setSortBy] = useState('risk_score')
  const [sortDesc, setSortDesc] = useState(true)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [showProgressNotification, setShowProgressNotification] = useState(false)

  // Scanning state (for button disable)
  const [activeScans, setActiveScans] = useState<Map<string, { running: boolean }>>(new Map())

  // Filters
  const [statusFilter, setStatusFilter] = useState<ActionStatus | ''>('')
  const [tierFilter, setTierFilter] = useState<ChannelTier | ''>('')
  const [assigneeFilter, setAssigneeFilter] = useState('')

  const [selectedChannel, setSelectedChannel] = useState<ChannelProfile | null>(null)
  const [showActionModal, setShowActionModal] = useState(false)
  const [showDetailsModal, setShowDetailsModal] = useState(false)

  const limit = 21

  useEffect(() => {
    loadData()
  }, [page, sortBy, sortDesc, statusFilter, tierFilter, assigneeFilter])

  const loadData = async () => {
    try {
      setLoading(true)
      const [channelsData, statsData] = await Promise.all([
        channelsAPI.list({ limit, offset: page * limit, sort_by: sortBy, sort_desc: sortDesc }),
        channelsAPI.getStats(),
      ])

      // Apply client-side filtering for mock data
      let filtered = channelsData.channels
      if (statusFilter) {
        filtered = filtered.filter(c => c.action_status === statusFilter)
      }
      if (tierFilter) {
        filtered = filtered.filter(c => c.tier === tierFilter)
      }
      if (assigneeFilter) {
        filtered = filtered.filter(c => c.assigned_to === assigneeFilter)
      }

      setChannels(filtered)
      setTotal(channelsData.total)
      setStats(statsData)
    } catch (err) {
      console.error('Failed to load channels:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSortChange = (option: SortOption) => {
    setSortBy(option.field)
    setSortDesc(option.desc)
    setPage(0)
  }

  const handleUpdateChannel = (channelId: string, updates: Partial<ChannelProfile>) => {
    // Mock update - in production, this would call an API
    setChannels(prev => prev.map(c =>
      c.channel_id === channelId ? { ...c, ...updates, last_action_date: new Date().toISOString() } : c
    ))
    setShowActionModal(false)
    setSelectedChannel(null)
  }

  const showToast = (message: string) => {
    setToastMessage(message)
    setTimeout(() => setToastMessage(null), 5000)
  }

  const handleScanAllVideos = async (channel: ChannelProfile) => {
    const channelId = channel.channel_id

    // Mark as scanning
    setActiveScans(prev => new Map(prev).set(channelId, { running: true }))

    try {
      const response = await fetch(`/api/channels/${channelId}/scan-all-videos`, {
        method: 'POST'
      })

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`)
      }

      const result = await response.json()

      // Show only the progress notification, not the toast
      setShowProgressNotification(true)

      // Clear after 3 seconds
      setTimeout(() => {
        setActiveScans(prev => {
          const newMap = new Map(prev)
          newMap.delete(channelId)
          return newMap
        })
      }, 3000)
    } catch (error) {
      console.error('Failed to scan videos:', error)
      showToast(`❌ Failed to queue videos: ${error instanceof Error ? error.message : 'Unknown error'}`)

      setTimeout(() => {
        setActiveScans(prev => {
          const newMap = new Map(prev)
          newMap.delete(channelId)
          return newMap
        })
      }, 3000)
    }
  }

  const handleDeepScan = async (channel: ChannelProfile) => {
    const channelId = channel.channel_id
    const maxVideos = 50

    // Mark as scanning
    setActiveScans(prev => new Map(prev).set(channelId, { running: true }))

    try {
      const response = await fetch(`/api/discovery/discover/channel/${channelId}/scan?max_videos=${maxVideos}`, {
        method: 'POST'
      })

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`)
      }

      const result = await response.json()

      // Show only the progress notification, not the toast
      setShowProgressNotification(true)

      // Reload after showing results
      setTimeout(() => {
        setActiveScans(prev => {
          const newMap = new Map(prev)
          newMap.delete(channelId)
          return newMap
        })
        window.location.reload()
      }, 2000)
    } catch (error) {
      console.error('Failed to discover videos:', error)
      showToast(`❌ Failed to discover videos: ${error instanceof Error ? error.message : 'Unknown error'}`)

      setTimeout(() => {
        setActiveScans(prev => {
          const newMap = new Map(prev)
          newMap.delete(channelId)
          return newMap
        })
      }, 3000)
    }
  }

  const getTierColor = (tier: ChannelTier) => {
    switch (tier) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-300'
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-300'
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 'low': return 'bg-green-100 text-green-800 border-green-300'
      case 'minimal': return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  const getActionStatusColor = (status?: ActionStatus) => {
    if (!status) return 'bg-gray-100 text-gray-600 border-gray-300'
    switch (status) {
      case 'new': return 'bg-blue-100 text-blue-800 border-blue-300'
      case 'in_review': return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 'legal_action': return 'bg-red-100 text-red-800 border-red-300'
      case 'resolved': return 'bg-green-100 text-green-800 border-green-300'
      case 'monitoring': return 'bg-purple-100 text-purple-800 border-purple-300'
    }
  }

  const getActionStatusLabel = (status?: ActionStatus) => {
    if (!status) return 'Not Reviewed'
    return status.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
  }

  const getPriorityBadge = (channel: ChannelProfile) => {
    // High priority: CRITICAL tier + infringements + not resolved
    if (channel.tier === 'critical' && channel.confirmed_infringements > 0 && channel.action_status !== 'resolved') {
      return (
        <span className="px-2 py-1 text-xs font-bold bg-red-600 text-white rounded-full animate-pulse">
          URGENT
        </span>
      )
    }
    // Medium priority: HIGH tier + recent infringements
    if (channel.tier === 'high' && channel.confirmed_infringements > 0 && !channel.action_status) {
      return (
        <span className="px-2 py-1 text-xs font-bold bg-orange-500 text-white rounded-full">
          NEEDS REVIEW
        </span>
      )
    }
    return null
  }

  // Calculate pipeline stats
  const pipelineStats = {
    new: channels.filter(c => !c.action_status || c.action_status === 'new').length,
    in_review: channels.filter(c => c.action_status === 'in_review').length,
    legal_action: channels.filter(c => c.action_status === 'legal_action').length,
    resolved: channels.filter(c => c.action_status === 'resolved').length,
    monitoring: channels.filter(c => c.action_status === 'monitoring').length,
  }

  if (loading && channels.length === 0) {
    return <div className="text-center py-12">Loading...</div>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Channel Enforcement Dashboard</h2>
          <p className="text-gray-600">{total} channels tracked · Logged in as: {user?.name || 'Guest'}</p>
        </div>
        <button
          onClick={() => navigate('/dashboards/vision')}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-800 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Scan History
        </button>
      </div>

      {/* Pipeline Overview */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow-lg p-6 border border-blue-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Enforcement Pipeline</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white rounded-lg p-4 shadow border-l-4 border-blue-500">
            <p className="text-sm font-medium text-gray-600">New / Not Reviewed</p>
            <p className="text-3xl font-bold text-blue-600">{pipelineStats.new}</p>
          </div>
          <div className="bg-white rounded-lg p-4 shadow border-l-4 border-yellow-500">
            <p className="text-sm font-medium text-gray-600">In Review</p>
            <p className="text-3xl font-bold text-yellow-600">{pipelineStats.in_review}</p>
          </div>
          <div className="bg-white rounded-lg p-4 shadow border-l-4 border-red-500">
            <p className="text-sm font-medium text-gray-600">Legal Action</p>
            <p className="text-3xl font-bold text-red-600">{pipelineStats.legal_action}</p>
          </div>
          <div className="bg-white rounded-lg p-4 shadow border-l-4 border-purple-500">
            <p className="text-sm font-medium text-gray-600">Monitoring</p>
            <p className="text-3xl font-bold text-purple-600">{pipelineStats.monitoring}</p>
          </div>
          <div className="bg-white rounded-lg p-4 shadow border-l-4 border-green-500">
            <p className="text-sm font-medium text-gray-600">Resolved</p>
            <p className="text-3xl font-bold text-green-600">{pipelineStats.resolved}</p>
          </div>
        </div>
      </div>

      {/* Filters & Sort */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Sort By</label>
            <select
              value={`${sortBy}:${sortDesc}`}
              onChange={(e) => {
                const option = SORT_OPTIONS.find(opt => `${opt.field}:${opt.desc}` === e.target.value)
                if (option) handleSortChange(option)
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={`${opt.field}:${opt.desc}`} value={`${opt.field}:${opt.desc}`}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Action Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ActionStatus | '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="new">New</option>
              <option value="in_review">In Review</option>
              <option value="legal_action">Legal Action</option>
              <option value="monitoring">Monitoring</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Risk Tier</label>
            <select
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value as ChannelTier | '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Tiers</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="minimal">Minimal</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Assigned To</label>
            <select
              value={assigneeFilter}
              onChange={(e) => setAssigneeFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Team Members</option>
              <option value={user?.name || 'Admin User'}>Me</option>
              <option value="Legal Team">Legal Team</option>
              <option value="Unassigned">Unassigned</option>
            </select>
          </div>
        </div>
      </div>

      {/* Channel Grid - Simplified Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {channels.map((channel) => {
          const videosScanned = channel.confirmed_infringements + channel.videos_cleared
          const infringementRate = videosScanned > 0 ? (channel.confirmed_infringements / videosScanned) * 100 : 0

          return (
            <div
              key={channel.channel_id}
              onClick={() => {
                setSelectedChannel(channel)
                setShowDetailsModal(true)
              }}
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
                      onError={(e) => {
                        console.error('Image failed to load:', channel.thumbnail_url)
                      }}
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
                  <span className={`px-2 py-1 text-xs font-bold rounded-full border bg-white ${getTierColor(channel.tier)}`}>
                    {channel.tier.toUpperCase()}
                  </span>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full border bg-white ${getActionStatusColor(channel.action_status)}`}>
                    {getActionStatusLabel(channel.action_status)}
                  </span>
                </div>

                {/* Priority Badge - Top Right */}
                <div className="absolute top-3 right-3">
                  {getPriorityBadge(channel)}
                </div>
              </div>

              {/* Main Metrics - Only Key Stats */}
              <div className="p-5">
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {/* Risk Score */}
                  <div className="text-center">
                    <div className="text-3xl font-bold text-gray-900">{channel.risk_score}</div>
                    <div className="text-xs text-gray-500 mt-1">Risk</div>
                  </div>

                  {/* Infringement Count */}
                  <div className="text-center">
                    <div className="text-3xl font-bold text-red-600">{channel.confirmed_infringements}</div>
                    <div className="text-xs text-gray-500 mt-1">Violations</div>
                  </div>

                  {/* Infringement Rate */}
                  <div className="text-center">
                    <div className={`text-3xl font-bold ${
                      infringementRate > 50 ? 'text-red-600' :
                      infringementRate > 25 ? 'text-orange-600' :
                      infringementRate > 0 ? 'text-yellow-600' :
                      'text-green-600'
                    }`}>
                      {infringementRate.toFixed(0)}%
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Rate</div>
                  </div>
                </div>

                {/* Secondary Info */}
                <div className="pt-3 border-t border-gray-200 text-sm text-gray-600 space-y-1">
                  <div className="flex justify-between">
                    <span>Scanned:</span>
                    <span className="font-medium">{videosScanned} / {channel.total_videos_found}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Subscribers:</span>
                    <span className="font-medium">
                      {channel.subscriber_count ? channel.subscriber_count.toLocaleString() : 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Channel Videos:</span>
                    <span className="font-medium">
                      {channel.video_count ? channel.video_count.toLocaleString() : 'N/A'}
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

                {/* Action Buttons */}
                <div className="mt-4 pt-3 border-t border-gray-200 flex gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleScanAllVideos(channel)
                    }}
                    className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                    disabled={activeScans.has(channel.channel_id)}
                    title="Queue all unscanned videos for Gemini vision analysis (skips already analyzed videos)"
                  >
                    📹 Scan All Videos
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeepScan(channel)
                    }}
                    className="flex-1 px-3 py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                    disabled={activeScans.has(channel.channel_id)}
                    title={`Fetch the latest 50 videos from this YouTube channel${channel.video_count && channel.video_count >= 50 ? ' (channel has 50+ videos)' : ''}`}
                  >
                    🔍 Discover
                  </button>
                </div>

              </div>
            </div>
          )
        })}
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center">
        <button
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page === 0}
          className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <span className="text-gray-600">
          Page {page + 1} of {Math.ceil(total / limit)}
        </span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={(page + 1) * limit >= total}
          className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>

      {/* Details Modal */}
      {showDetailsModal && selectedChannel && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowDetailsModal(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                  {/* Thumbnail or fallback */}
                  {selectedChannel.thumbnail_url ? (
                    <img
                      src={selectedChannel.thumbnail_url}
                      alt={selectedChannel.channel_title}
                      className="w-16 h-16 rounded-full object-cover shadow-lg bg-gray-200"
                      referrerPolicy="no-referrer"
                      crossOrigin="anonymous"
                    />
                  ) : (
                    <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-pink-600 rounded-full flex items-center justify-center text-white text-2xl font-bold shadow-lg">
                      {selectedChannel.channel_title.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900">{selectedChannel.channel_title}</h3>
                    <a
                      href={`https://www.youtube.com/channel/${selectedChannel.channel_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline text-sm"
                    >
                      View on YouTube →
                    </a>
                  </div>
                </div>
                <button
                  onClick={() => setShowDetailsModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Badges */}
              <div className="flex items-center gap-2 mb-6 flex-wrap">
                {getPriorityBadge(selectedChannel)}
                <span className={`px-3 py-1 text-sm font-bold rounded-full border ${getTierColor(selectedChannel.tier)}`}>
                  {selectedChannel.tier.toUpperCase()} TIER
                </span>
                <span className={`px-3 py-1 text-sm font-medium rounded-full border ${getActionStatusColor(selectedChannel.action_status)}`}>
                  {getActionStatusLabel(selectedChannel.action_status)}
                </span>
              </div>

              {/* Key Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <div className="text-sm text-gray-600 mb-1">Risk Score</div>
                  <div className="text-3xl font-bold text-gray-900">{selectedChannel.risk_score}<span className="text-lg text-gray-500">/100</span></div>
                </div>
                <div className="bg-red-50 rounded-lg p-4 border border-red-200">
                  <div className="text-sm text-gray-600 mb-1">Infringements</div>
                  <div className="text-3xl font-bold text-red-600">{selectedChannel.confirmed_infringements}</div>
                  <div className="text-xs text-gray-500">
                    {selectedChannel.confirmed_infringements + selectedChannel.videos_cleared > 0
                      ? `${((selectedChannel.confirmed_infringements / (selectedChannel.confirmed_infringements + selectedChannel.videos_cleared)) * 100).toFixed(1)}% rate`
                      : 'No scans yet'}
                  </div>
                </div>
                <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                  <div className="text-sm text-gray-600 mb-1">Cleared</div>
                  <div className="text-3xl font-bold text-green-600">{selectedChannel.videos_cleared}</div>
                </div>
                <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                  <div className="text-sm text-gray-600 mb-1">Total Found</div>
                  <div className="text-3xl font-bold text-blue-600">{selectedChannel.total_videos_found}</div>
                  <div className="text-xs text-gray-500">
                    {selectedChannel.total_videos_found - selectedChannel.confirmed_infringements - selectedChannel.videos_cleared} unscanned
                  </div>
                </div>
              </div>

              {/* Additional Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div className="space-y-3">
                  <h4 className="font-bold text-gray-900">Channel Information</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between py-2 border-b border-gray-200">
                      <span className="text-gray-600">Subscribers:</span>
                      <span className="font-medium">{selectedChannel.subscriber_count?.toLocaleString() || 'Unknown'}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-200">
                      <span className="text-gray-600">Last Scanned:</span>
                      <span className="font-medium">
                        {selectedChannel.last_scanned_at
                          ? new Date(selectedChannel.last_scanned_at).toLocaleDateString()
                          : 'Never'}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-200">
                      <span className="text-gray-600">Discovered:</span>
                      <span className="font-medium">{new Date(selectedChannel.discovered_at).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-200">
                      <span className="text-gray-600">Last Upload:</span>
                      <span className="font-medium">
                        {selectedChannel.last_upload_date
                          ? new Date(selectedChannel.last_upload_date).toLocaleDateString()
                          : 'Unknown'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <h4 className="font-bold text-gray-900">Enforcement Status</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between py-2 border-b border-gray-200">
                      <span className="text-gray-600">Status:</span>
                      <span className="font-medium">{getActionStatusLabel(selectedChannel.action_status)}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-200">
                      <span className="text-gray-600">Assigned To:</span>
                      <span className="font-medium">{selectedChannel.assigned_to || 'Unassigned'}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-200">
                      <span className="text-gray-600">Last Action:</span>
                      <span className="font-medium">
                        {selectedChannel.last_action_date
                          ? new Date(selectedChannel.last_action_date).toLocaleDateString()
                          : 'None'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Notes */}
              {selectedChannel.notes && (
                <div className="mb-6">
                  <h4 className="font-bold text-gray-900 mb-2">Notes</h4>
                  <div className="p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded">
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">{selectedChannel.notes}</p>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowDetailsModal(false)
                    setShowActionModal(true)
                  }}
                  className="px-4 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Take Action / Update Status
                </button>
                <a
                  href={`/videos?channel=${encodeURIComponent(selectedChannel.channel_id)}`}
                  className="px-4 py-3 bg-gray-600 text-white font-medium rounded-lg hover:bg-gray-700 transition-colors text-center"
                >
                  View All Videos
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Action Modal */}
      {showActionModal && selectedChannel && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-gray-900">
                  Update Channel Action
                </h3>
                <button
                  onClick={() => setShowActionModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <p className="text-gray-600 mb-6">{selectedChannel.channel_title}</p>

              <form onSubmit={(e) => {
                e.preventDefault()
                const formData = new FormData(e.currentTarget)
                handleUpdateChannel(selectedChannel.channel_id, {
                  action_status: formData.get('status') as ActionStatus,
                  assigned_to: formData.get('assigned_to') as string,
                  notes: formData.get('notes') as string,
                })
              }}>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Action Status
                    </label>
                    <select
                      name="status"
                      defaultValue={selectedChannel.action_status || 'new'}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="new">New</option>
                      <option value="in_review">In Review</option>
                      <option value="legal_action">Legal Action</option>
                      <option value="monitoring">Monitoring</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Assign To
                    </label>
                    <select
                      name="assigned_to"
                      defaultValue={selectedChannel.assigned_to || ''}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Unassigned</option>
                      <option value={user?.name || 'Admin User'}>{user?.name || 'Me'}</option>
                      <option value="Legal Team">Legal Team</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Notes
                    </label>
                    <textarea
                      name="notes"
                      defaultValue={selectedChannel.notes || ''}
                      rows={4}
                      placeholder="Add notes about actions taken, next steps, etc..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div className="flex gap-3 mt-6">
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Save Changes
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowActionModal(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 font-medium rounded-lg hover:bg-gray-300 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Scan Progress Notification */}
      <ScanProgressNotification
        show={showProgressNotification}
        onClose={() => setShowProgressNotification(false)}
      />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-4 right-4 bg-gray-900 text-white px-6 py-3 rounded-lg shadow-2xl animate-fade-in z-50">
          {toastMessage}
        </div>
      )}
    </div>
  )
}
