import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { videosAPI } from '../api/videos'
import { channelsAPI } from '../api/channels'
import AnalysisDetailModal from '../components/AnalysisDetailModal'
import ScanProgressModal from '../components/ScanProgressModal'
import ActiveScansOverlay from '../components/ActiveScansOverlay'
import ScanProgressNotification from '../components/ScanProgressNotification'
import type { VideoMetadata, VideoStatus, ChannelProfile, VisionAnalysis } from '../types'

type SortOption = {
  label: string
  field: string
  desc: boolean
}

const SORT_OPTIONS: SortOption[] = [
  { label: '🔥 Highest Risk (Priority)', field: 'scan_priority', desc: true },
  { label: '⚠️ Channel Risk', field: 'channel_risk', desc: true },
  { label: '📊 Video Risk', field: 'video_risk', desc: true },
  { label: '👁️ Highest Views', field: 'view_count', desc: true },
  { label: '⏱️ Longest Duration', field: 'duration_seconds', desc: true },
  { label: '🆕 Most Recently Found', field: 'discovered_at', desc: true },
  { label: '📅 Most Recently Uploaded', field: 'published_at', desc: true },
]

export default function VideoListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [videos, setVideos] = useState<VideoMetadata[]>([])
  const [channels, setChannels] = useState<ChannelProfile[]>([])
  const [ipConfigs, setIpConfigs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [sortBy, setSortBy] = useState('scan_priority')
  const [sortDesc, setSortDesc] = useState(true)
  const [modalVideoId, setModalVideoId] = useState<string | null>(null)
  const [scanProgress, setScanProgress] = useState<Map<string, any>>(new Map()) // SINGLE SOURCE OF TRUTH for all progress
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false)
  const [selectedAnalysis, setSelectedAnalysis] = useState<{ video: VideoMetadata; analysis: VisionAnalysis } | null>(null)
  const [scanningInProgress, setScanningInProgress] = useState<Set<string>>(new Set())
  const [filterPanelOpen, setFilterPanelOpen] = useState(false)
  const [showProgressNotification, setShowProgressNotification] = useState(false)

  // Filters
  const [channelFilter, setChannelFilter] = useState<string>(searchParams.get('channel') || '')
  const [statusFilter, setStatusFilter] = useState<VideoStatus | ''>(searchParams.get('status') as VideoStatus || '')
  const [ipConfigFilter, setIpConfigFilter] = useState<string>(searchParams.get('ip_config') || '')

  const limit = 20

  // Load channels and IP configs for dropdowns
  useEffect(() => {
    loadChannels()
    loadIpConfigs()
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

  const loadIpConfigs = async () => {
    try {
      const response = await fetch('http://localhost:8080/api/config/list')
      if (!response.ok) throw new Error('Failed to load IP configs')
      const data = await response.json()
      setIpConfigs(data.configs)
    } catch (err) {
      console.error('Failed to load IP configs:', err)
    }
  }

  useEffect(() => {
    // Update filters from URL params
    const channel = searchParams.get('channel') || ''
    const status = searchParams.get('status') as VideoStatus || ''
    const ipConfig = searchParams.get('ip_config') || ''

    setChannelFilter(channel)
    setStatusFilter(status)
    setIpConfigFilter(ipConfig)
  }, [searchParams])

  useEffect(() => {
    loadVideos()
  }, [page, sortBy, sortDesc, channelFilter, statusFilter, ipConfigFilter])

  const loadVideos = async () => {
    try {
      setLoading(true)
      const data = await videosAPI.list({
        limit: ipConfigFilter ? 1000 : limit, // Load more if filtering by IP config
        offset: ipConfigFilter ? 0 : page * limit,
        sort_by: sortBy,
        sort_desc: sortDesc,
        channel_id: channelFilter || undefined,
        status: statusFilter || undefined,
        has_ip_match: true, // Only show videos with IP configs (can be scanned)
      })

      // Filter by IP config on client side if selected
      let filteredVideos = data.videos
      if (ipConfigFilter) {
        filteredVideos = data.videos.filter(video =>
          video.matched_ips && video.matched_ips.includes(ipConfigFilter)
        )
        // Apply client-side pagination
        const start = page * limit
        const end = start + limit
        setVideos(filteredVideos.slice(start, end))
        setTotal(filteredVideos.length)
      } else {
        setVideos(data.videos)
        setTotal(data.total)
      }
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

  const handleFilterChange = (type: 'channel' | 'status' | 'ip_config', value: string) => {
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
    } else if (type === 'ip_config') {
      if (value) {
        params.set('ip_config', value)
      } else {
        params.delete('ip_config')
      }
      setIpConfigFilter(value)
    }

    setSearchParams(params)
    setPage(0)
  }

  const clearFilters = () => {
    setSearchParams({})
    setChannelFilter('')
    setStatusFilter('')
    setIpConfigFilter('')
    setPage(0)
  }

  const handleScanVideo = async (video: VideoMetadata) => {
    // Mark as scanning to prevent double-clicks
    setScanningInProgress(prev => new Set(prev).add(video.video_id))

    try {
      // Trigger the scan via API
      await videosAPI.scanVideo(video.video_id)
      // Show progress notification
      setShowProgressNotification(true)
      // ActiveScansOverlay will automatically pick up the processing video
    } catch (error) {
      console.error('Failed to start scan:', error)
      // Remove from scanning state on error
      setScanningInProgress(prev => {
        const next = new Set(prev)
        next.delete(video.video_id)
        return next
      })
    }
  }

  const handleScanComplete = () => {
    // ONLY reload videos - do NOT close modal
    // Modal should stay open until user explicitly closes it
    loadVideos()
  }

  const handleViewProgress = (videoId: string) => {
    // Just set the video ID - modal will read from shared scanProgress state
    setModalVideoId(videoId)
  }

  const activeFiltersCount = [channelFilter, statusFilter, ipConfigFilter].filter(Boolean).length

  if (loading && videos.length === 0) {
    return <div className="text-center py-12">Loading...</div>
  }

  return (
    <>
    {/* Header */}
    <div className="mb-6 flex items-center justify-between">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Video Library</h2>
        <p className="text-gray-600">{total} videos discovered</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Scan History Button */}
        <button
          onClick={() => navigate('/dashboards/vision')}
          className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-800 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Scan History
        </button>

        {/* Filter Toggle Button */}
        <button
          onClick={() => setFilterPanelOpen(!filterPanelOpen)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 active:scale-95 transition-all"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          Filters {activeFiltersCount > 0 && `(${activeFiltersCount})`}
        </button>
      </div>
    </div>

    {/* Video Grid - Full width, not affected by filter */}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {videos.map((video) => {
          // Determine overall infringement status from multi-IP format
          let hasInfringement = false
          let confidence = 0
          let infringementCount = 0

          if (video.vision_analysis?.ip_results && video.vision_analysis.ip_results.length > 0) {
            // Check if any IP has infringement
            hasInfringement = video.vision_analysis.ip_results.some(ip => ip.contains_infringement)
            infringementCount = video.vision_analysis.ip_results.filter(ip => ip.contains_infringement).length
            // Average infringement likelihood across all IPs
            const avgLikelihood = video.vision_analysis.ip_results.reduce((sum, ip) => sum + ip.infringement_likelihood, 0) / video.vision_analysis.ip_results.length
            confidence = Math.round(avgLikelihood)
          }

          return (
          <div key={video.video_id} className={`bg-white rounded-lg shadow overflow-hidden hover:shadow-xl transition-shadow ${
            video.status === 'analyzed' && hasInfringement ? 'border-2 border-red-500' :
            video.status === 'analyzed' && !hasInfringement ? 'border-2 border-green-500' : ''
          }`}>
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
            <div className="p-4 flex flex-col">
              <a
                href={`https://youtube.com/watch?v=${video.video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <h3 className="font-medium text-gray-900 hover:text-blue-600 line-clamp-2 text-sm mb-2 transition-colors h-10">
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

              {/* Risk Score */}
              {video.scan_priority !== undefined && (
                <div className="mt-2 p-2 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-gray-700">Scan Priority</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                      (video.scan_priority >= 90) ? 'bg-red-600 text-white' :
                      (video.scan_priority >= 70) ? 'bg-orange-600 text-white' :
                      (video.scan_priority >= 50) ? 'bg-yellow-600 text-white' :
                      (video.scan_priority >= 30) ? 'bg-blue-600 text-white' :
                      'bg-gray-600 text-white'
                    }`}>
                      {video.scan_priority}/100
                    </span>
                  </div>
                  <div className="text-xs text-gray-600 flex items-center justify-between">
                    <span>Tier: <span className="font-medium">{video.priority_tier}</span></span>
                    <span className="text-gray-500">CH:{video.channel_risk} | VID:{video.video_risk}</span>
                  </div>
                </div>
              )}

              {/* Infringement Summary (for analyzed videos) */}
              {video.status === 'analyzed' && video.vision_analysis?.ip_results && video.vision_analysis.ip_results.length > 0 && (
                <div className="mt-2 p-2 rounded-lg border" style={{
                  backgroundColor: hasInfringement ? '#fee2e2' : '#d1fae5',
                  borderColor: hasInfringement ? '#ef4444' : '#10b981'
                }}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-bold ${hasInfringement ? 'text-red-900' : 'text-green-900'}`}>
                      {hasInfringement ? '⚠️ INFRINGEMENT DETECTED' : '✅ NO INFRINGEMENT'}
                    </span>
                    <span className={`text-xs font-medium ${hasInfringement ? 'text-red-700' : 'text-green-700'}`}>
                      {confidence}% likelihood
                    </span>
                  </div>

                  {/* IP Results Summary */}
                  <div className="text-xs text-gray-700 mt-1">
                    {hasInfringement && infringementCount > 0 && (
                      <div className="font-medium">
                        {infringementCount} of {video.vision_analysis.ip_results.length} IP{video.vision_analysis.ip_results.length > 1 ? 's' : ''} flagged
                      </div>
                    )}
                    <div className="flex flex-wrap gap-1 mt-1">
                      {video.vision_analysis.ip_results.slice(0, 2).map((ipResult, idx) => (
                        <div key={idx} className="flex items-center gap-1">
                          <span
                            className={`px-1.5 py-0.5 rounded text-xs ${
                              ipResult.contains_infringement
                                ? 'bg-red-200 text-red-900'
                                : 'bg-green-200 text-green-900'
                            }`}
                          >
                            {ipResult.ip_name}
                          </span>
                          {ipResult.fair_use_applies && (
                            <span className="px-1.5 py-0.5 rounded text-xs bg-blue-200 text-blue-900">
                              Fair Use
                            </span>
                          )}
                        </div>
                      ))}
                      {video.vision_analysis.ip_results.length > 2 && (
                        <span className="px-1.5 py-0.5 text-xs text-gray-600">
                          +{video.vision_analysis.ip_results.length - 2} more
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="mt-3 space-y-2">
                {/* View Progress Button (for processing videos) */}
                {video.status === 'processing' && (
                  <button
                    onClick={() => handleViewProgress(video.video_id)}
                    className="flex items-center justify-center gap-2 w-full text-center px-3 py-2 bg-orange-600 text-white text-xs font-medium rounded-lg hover:bg-orange-700 active:scale-95 transition-all"
                  >
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    View Progress
                  </button>
                )}

                {/* Scan Now / Retry Button (for discovered or failed videos) */}
                {(video.status === 'discovered' || video.status === 'failed') && (
                  <button
                    onClick={() => handleScanVideo(video)}
                    disabled={scanningInProgress.has(video.video_id)}
                    className={`flex items-center justify-center gap-2 w-full text-center px-3 py-2 text-white text-xs font-medium rounded-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 ${
                      video.status === 'failed' ? 'bg-orange-600 hover:bg-orange-700' : 'bg-blue-600 hover:bg-blue-700'
                    }`}
                  >
                    {scanningInProgress.has(video.video_id) ? (
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        {video.status === 'failed' ? (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        ) : (
                          <>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                          </>
                        )}
                      </svg>
                    )}
                    {scanningInProgress.has(video.video_id)
                      ? 'Queuing...'
                      : video.status === 'failed' ? 'Retry Scan' : 'Scan Now'}
                  </button>
                )}

                {/* View Analysis Details Button (only for analyzed videos) */}
                {video.status === 'analyzed' && video.vision_analysis && (
                  <button
                    onClick={() => {
                      setSelectedAnalysis({ video, analysis: video.vision_analysis! })
                      setAnalysisModalOpen(true)
                    }}
                    className="flex items-center justify-center gap-2 w-full text-center px-3 py-2 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 active:scale-95 transition-all"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    View Analysis Details
                  </button>
                )}

                {/* View on YouTube Button */}
                <a
                  href={`https://youtube.com/watch?v=${video.video_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full text-center px-3 py-2 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                  </svg>
                  Watch on YouTube
                </a>
              </div>
            </div>
          </div>
          )
        })}
    </div>

    {/* Pagination */}
    <div className="flex justify-between items-center mt-8">
      <button
        onClick={() => setPage((p) => Math.max(0, p - 1))}
        disabled={page === 0}
        className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
      >
        Previous
      </button>
      <span className="text-gray-600">
        Page {page + 1} of {Math.ceil(total / limit)}
      </span>
      <button
        onClick={() => setPage((p) => p + 1)}
        disabled={(page + 1) * limit >= total}
        className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
      >
        Next
      </button>
    </div>

    {/* Filter Panel - Slide-in overlay (all screen sizes) */}
    <>
      {/* Backdrop overlay */}
      {filterPanelOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setFilterPanelOpen(false)}
        />
      )}

      {/* Filter Panel */}
      <div className={`
        fixed z-50 bg-white shadow-2xl transition-transform duration-300 ease-in-out
        ${filterPanelOpen ? 'translate-x-0' : 'translate-x-full'}
        top-0 right-0 h-full w-80 overflow-y-auto
      `}>
        {/* Header with Close Button */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">Filters & Sort</h3>
          <button
            onClick={() => setFilterPanelOpen(false)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-6 p-4">
          {/* Sort Section */}
          <div className="bg-white rounded-lg shadow-md border border-gray-200 p-4">
            <label className="block text-xs font-bold text-gray-900 uppercase tracking-wider mb-3">
              Sort By
            </label>
            <select
              value={`${sortBy}:${sortDesc}`}
              onChange={(e) => {
                const option = SORT_OPTIONS.find(
                  (opt) => `${opt.field}:${opt.desc}` === e.target.value
                )
                if (option) handleSortChange(option)
              }}
              className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={`${opt.field}:${opt.desc}`} value={`${opt.field}:${opt.desc}`}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Filter Section */}
          <div className="bg-white rounded-lg shadow-md border border-gray-200 p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b">
              <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">Filters</h3>
              {activeFiltersCount > 0 && (
                <button
                  onClick={clearFilters}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  Clear ({activeFiltersCount})
                </button>
              )}
            </div>

            {/* IP Config Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                IP Configuration
              </label>
              <select
                value={ipConfigFilter}
                onChange={(e) => handleFilterChange('ip_config', e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All IPs ({ipConfigs.length})</option>
                {ipConfigs.map((config) => (
                  <option key={config.id} value={config.id}>
                    {config.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Channel Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Channel
              </label>
              <select
                value={channelFilter}
                onChange={(e) => handleFilterChange('channel', e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All channels ({channels.length})</option>
                {channels.map((channel) => (
                  <option key={channel.channel_id} value={channel.channel_id}>
                    {channel.channel_title} ({channel.total_videos_found})
                  </option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All statuses</option>
                <option value="discovered">Discovered</option>
                <option value="processing">Processing</option>
                <option value="analyzed">Analyzed</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>

          {/* Apply Button */}
          <button
            onClick={() => setFilterPanelOpen(false)}
            className="w-full px-4 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 active:scale-95 transition-all"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </>

    {/* Modals and Overlays (outside main layout) */}
    {/* Active Scans Overlay (bottom-right) - shows ALL processing videos */}
    <ActiveScansOverlay
      onViewProgress={handleViewProgress}
      onScansChanged={handleScanComplete}
      scanProgress={scanProgress}
      setScanProgress={setScanProgress}
    />

    {/* Scan Progress Modal (detailed view) */}
    {modalVideoId && (
      <ScanProgressModal
        videoId={modalVideoId}
        scanProgress={scanProgress}
        onClose={() => setModalVideoId(null)}
      />
    )}

    {/* Scan Progress Notification */}
    <ScanProgressNotification
      show={showProgressNotification}
      onClose={() => setShowProgressNotification(false)}
    />

    {/* Analysis Detail Modal */}
    {selectedAnalysis && (
      <AnalysisDetailModal
        isOpen={analysisModalOpen}
        onClose={() => {
          setAnalysisModalOpen(false)
          setSelectedAnalysis(null)
        }}
        analysis={selectedAnalysis.analysis}
        videoTitle={selectedAnalysis.video.title}
        videoId={selectedAnalysis.video.video_id}
      />
    )}
    </>
  )
}
