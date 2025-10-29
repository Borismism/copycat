import { useState, useEffect } from 'react'
import { channelsAPI } from '../api/channels'
import type { ChannelProfile, ChannelStats, ChannelTier } from '../types'

type SortOption = {
  label: string
  field: string
  desc: boolean
}

const SORT_OPTIONS: SortOption[] = [
  { label: 'Highest Risk Score', field: 'risk_score', desc: true },
  { label: 'Most Videos Found', field: 'total_videos_found', desc: true },
  { label: 'Most Recently Scanned', field: 'last_scanned_at', desc: true },
  { label: 'Most Recently Discovered', field: 'discovered_at', desc: true },
]

export default function ChannelListPage() {
  const [channels, setChannels] = useState<ChannelProfile[]>([])
  const [stats, setStats] = useState<ChannelStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [sortBy, setSortBy] = useState('risk_score')
  const [sortDesc, setSortDesc] = useState(true)
  const limit = 20

  useEffect(() => {
    loadData()
  }, [page, sortBy, sortDesc])

  const loadData = async () => {
    try {
      setLoading(true)
      const [channelsData, statsData] = await Promise.all([
        channelsAPI.list({ limit, offset: page * limit, sort_by: sortBy, sort_desc: sortDesc }),
        channelsAPI.getStats(),
      ])
      setChannels(channelsData.channels)
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
    setPage(0) // Reset to first page on sort change
  }

  const getTierColor = (tier: ChannelTier) => {
    switch (tier) {
      case 'critical':
        return 'bg-red-100 text-red-800'
      case 'high':
        return 'bg-orange-100 text-orange-800'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800'
      case 'low':
        return 'bg-green-100 text-green-800'
      case 'minimal':
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getTierIcon = (tier: ChannelTier) => {
    switch (tier) {
      case 'critical':
        return '🔴'
      case 'high':
        return '🟠'
      case 'medium':
        return '🟡'
      case 'low':
        return '🟢'
      case 'minimal':
        return '⚪'
    }
  }

  if (loading && channels.length === 0) {
    return <div className="text-center py-12">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Channels</h2>
          <p className="text-gray-600">{total} channels tracked</p>
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600">Sort by:</label>
          <select
            value={`${sortBy}:${sortDesc}`}
            onChange={(e) => {
              const option = SORT_OPTIONS.find(
                (opt) => `${opt.field}:${opt.desc}` === e.target.value
              )
              if (option) handleSortChange(option)
            }}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={`${opt.field}:${opt.desc}`} value={`${opt.field}:${opt.desc}`}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Risk Tier Distribution</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <p className="text-sm text-gray-600">🔴 Critical (80-100)</p>
              <p className="text-2xl font-bold text-red-600">{stats.critical}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">🟠 High (60-79)</p>
              <p className="text-2xl font-bold text-orange-600">{stats.high}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">🟡 Medium (40-59)</p>
              <p className="text-2xl font-bold text-yellow-600">{stats.medium}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">🟢 Low (20-39)</p>
              <p className="text-2xl font-bold text-green-600">{stats.low}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">⚪ Minimal (0-19)</p>
              <p className="text-2xl font-bold text-gray-600">{stats.minimal}</p>
            </div>
          </div>
        </div>
      )}

      {/* Channel List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="divide-y divide-gray-200">
          {channels.map((channel) => (
            <div key={channel.channel_id} className="p-6 hover:bg-gray-50 transition-colors">
              <div className="flex items-start gap-4">
                {/* Channel Avatar Placeholder */}
                <div className="flex-shrink-0">
                  <div className="w-20 h-20 bg-gradient-to-br from-red-500 to-pink-600 rounded-full flex items-center justify-center text-white text-2xl font-bold shadow-lg">
                    {channel.channel_title.charAt(0).toUpperCase()}
                  </div>
                </div>

                {/* Channel Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-2xl">{getTierIcon(channel.tier)}</span>
                        <a
                          href={`https://www.youtube.com/channel/${channel.channel_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-lg font-semibold text-gray-900 hover:text-blue-600 transition-colors truncate"
                        >
                          {channel.channel_title}
                        </a>
                        <span className={`px-2 py-1 text-xs rounded-full whitespace-nowrap ${getTierColor(channel.tier)}`}>
                          {channel.tier}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mt-3">
                        <div>
                          <span className="text-gray-600">Risk Score:</span>
                          <span className="ml-2 font-semibold text-gray-900">{channel.risk_score}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Videos:</span>
                          <span className="ml-2 font-semibold text-gray-900">{channel.total_videos_found}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Infringements:</span>
                          <span className="ml-2 font-semibold text-red-600">
                            {channel.confirmed_infringements}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-600">Infringement Rate:</span>
                          <span className="ml-2 font-semibold text-orange-600">
                            {(channel.infringement_rate * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>

                      {channel.last_scanned_at && (
                        <p className="mt-3 text-xs text-gray-500">
                          Last scanned: {new Date(channel.last_scanned_at).toLocaleString()}
                        </p>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-col gap-2">
                      <a
                        href={`https://www.youtube.com/channel/${channel.channel_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2 whitespace-nowrap"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                        </svg>
                        View on YouTube
                      </a>
                      <a
                        href={`/videos?channel=${encodeURIComponent(channel.channel_id)}`}
                        className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors text-center whitespace-nowrap"
                      >
                        View Videos
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
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
    </div>
  )
}
