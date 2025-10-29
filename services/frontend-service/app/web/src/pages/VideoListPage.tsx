import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { videosAPI } from '../api/videos'
import { channelsAPI } from '../api/channels'
import type { VideoMetadata, VideoStatus, ChannelProfile } from '../types'

type SortOption = {
  label: string
  field: string
  desc: boolean
}

const SORT_OPTIONS: SortOption[] = [
  { label: 'Highest Views', field: 'view_count', desc: true },
  { label: 'Longest Duration', field: 'duration_seconds', desc: true },
  { label: 'Most Recently Found', field: 'discovered_at', desc: true },
  { label: 'Most Recently Uploaded', field: 'published_at', desc: true },
]

export default function VideoListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [videos, setVideos] = useState<VideoMetadata[]>([])
  const [channels, setChannels] = useState<ChannelProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [sortBy, setSortBy] = useState('view_count')
  const [sortDesc, setSortDesc] = useState(true)

  // Filters
  const [channelFilter, setChannelFilter] = useState<string>(searchParams.get('channel') || '')
  const [statusFilter, setStatusFilter] = useState<VideoStatus | ''>(searchParams.get('status') as VideoStatus || '')

  const limit = 20

  // Load channels for dropdown
  useEffect(() => {
    loadChannels()
  }, [])

  const loadChannels = async () => {
    try {
      console.log('Loading channels...')
      // Load all channels with pagination (API limit is 100 per request)
      let allChannels: ChannelProfile[] = []
      let offset = 0
      const limit = 100

      // Fetch up to 500 channels (5 pages)
      while (offset < 500) {
        const data = await channelsAPI.list({
          limit,
          offset,
          sort_by: 'risk_score',
          sort_desc: true
        })
        allChannels = [...allChannels, ...data.channels]

        if (!data.has_more || data.channels.length < limit) {
          break // No more channels
        }
        offset += limit
      }

      console.log('Channels loaded:', allChannels.length, 'channels')
      setChannels(allChannels)
    } catch (err) {
      console.error('Failed to load channels:', err)
    }
  }

  useEffect(() => {
    // Update filters from URL params
    const channel = searchParams.get('channel') || ''
    const status = searchParams.get('status') as VideoStatus || ''

    setChannelFilter(channel)
    setStatusFilter(status)
  }, [searchParams])

  useEffect(() => {
    loadVideos()
  }, [page, sortBy, sortDesc, channelFilter, statusFilter])

  const loadVideos = async () => {
    try {
      setLoading(true)
      const data = await videosAPI.list({
        limit,
        offset: page * limit,
        sort_by: sortBy,
        sort_desc: sortDesc,
        channel_id: channelFilter || undefined,
        status: statusFilter || undefined,
      })
      setVideos(data.videos)
      setTotal(data.total)
    } catch (err) {
      console.error('Failed to load videos:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSortChange = (option: SortOption) => {
    setSortBy(option.field)
    setSortDesc(option.desc)
    setPage(0)
  }

  const handleFilterChange = (type: 'channel' | 'status', value: string) => {
    const params = new URLSearchParams(searchParams)

    if (type === 'channel') {
      if (value) {
        params.set('channel', value)
      } else {
        params.delete('channel')
      }
      setChannelFilter(value)
    } else if (type === 'status') {
      if (value) {
        params.set('status', value)
      } else {
        params.delete('status')
      }
      setStatusFilter(value as VideoStatus || '')
    }

    setSearchParams(params)
    setPage(0)
  }

  const clearFilters = () => {
    setSearchParams({})
    setChannelFilter('')
    setStatusFilter('')
    setPage(0)
  }

  const activeFiltersCount = [channelFilter, statusFilter].filter(Boolean).length

  if (loading && videos.length === 0) {
    return <div className="text-center py-12">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Video Library</h2>
          <p className="text-gray-600">{total} videos discovered</p>
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

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">Filters</h3>
          {activeFiltersCount > 0 && (
            <button
              onClick={clearFilters}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              Clear all ({activeFiltersCount})
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Channel Filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Channel</label>
            <select
              value={channelFilter}
              onChange={(e) => handleFilterChange('channel', e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All channels ({channels.length})</option>
              {channels.map((channel) => (
                <option key={channel.channel_id} value={channel.channel_id}>
                  {channel.channel_title} ({channel.total_videos_found} videos)
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All statuses</option>
              <option value="discovered">Discovered</option>
              <option value="processing">Processing</option>
              <option value="analyzed">Analyzed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

        </div>
      </div>

      {/* Video Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {videos.map((video) => (
          <div key={video.video_id} className="bg-white rounded-lg shadow overflow-hidden hover:shadow-xl transition-shadow">
            {/* Thumbnail - Clickable */}
            <a
              href={`https://youtube.com/watch?v=${video.video_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="block relative group"
            >
              {video.thumbnail_url ? (
                <>
                  <img
                    src={video.thumbnail_url}
                    alt={video.title}
                    className="w-full h-48 object-cover group-hover:opacity-90 transition-opacity"
                  />
                  {/* Play button overlay */}
                  <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black bg-opacity-20">
                    <div className="w-16 h-16 bg-red-600 rounded-full flex items-center justify-center">
                      <svg className="w-8 h-8 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z"/>
                      </svg>
                    </div>
                  </div>
                </>
              ) : (
                <div className="w-full h-48 bg-gray-200 flex items-center justify-center group-hover:bg-gray-300 transition-colors">
                  <span className="text-gray-400">No thumbnail</span>
                </div>
              )}
            </a>

            {/* Content */}
            <div className="p-4">
              <a
                href={`https://youtube.com/watch?v=${video.video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <h3 className="font-medium text-gray-900 hover:text-blue-600 line-clamp-2 text-sm mb-2 transition-colors">
                  {video.title}
                </h3>
              </a>
              <a
                href={`https://www.youtube.com/channel/${video.channel_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-gray-600 hover:text-blue-600 block mb-2 transition-colors"
              >
                {video.channel_title}
              </a>

              <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                <span>{video.view_count.toLocaleString()} views</span>
                {video.duration_seconds && (
                  <span>{Math.floor(video.duration_seconds / 60)}:{(video.duration_seconds % 60).toString().padStart(2, '0')}</span>
                )}
              </div>

              {/* IP Matches */}
              {video.matched_ips.length > 0 && (
                <div className="mt-2">
                  <div className="flex flex-wrap gap-1">
                    {video.matched_ips.slice(0, 2).map((ip) => (
                      <span
                        key={ip}
                        className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full"
                      >
                        {ip.replace(' AI Content', '')}
                      </span>
                    ))}
                    {video.matched_ips.length > 2 && (
                      <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                        +{video.matched_ips.length - 2}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Status */}
              <div className="mt-2">
                <span
                  className={`px-2 py-1 text-xs rounded-full ${
                    video.status === 'discovered'
                      ? 'bg-blue-100 text-blue-800'
                      : video.status === 'processing'
                      ? 'bg-yellow-100 text-yellow-800'
                      : video.status === 'analyzed'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {video.status}
                </span>
              </div>

              {/* View on YouTube Button */}
              <a
                href={`https://youtube.com/watch?v=${video.video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 flex items-center justify-center gap-2 w-full text-center px-3 py-2 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                Watch on YouTube
              </a>
            </div>
          </div>
        ))}
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
