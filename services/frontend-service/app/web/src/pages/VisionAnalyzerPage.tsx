import { useState, useEffect, useRef, useCallback } from 'react'
import useSWR from 'swr'
import { Link } from 'react-router-dom'
import { visionAPI } from '../api/vision'
import { videosAPI } from '../api/videos'
import AnalysisDetailModal from '../components/AnalysisDetailModal'
import ScanProgressNotification from '../components/ScanProgressNotification'
import { usePermissions } from '../hooks/usePermissions'

interface ScanHistory {
  scan_id: string
  scan_type: 'video_single'
  channel_id?: string
  channel_title?: string
  video_id: string
  video_title: string
  started_at: { seconds: number } | string | number
  completed_at?: { seconds: number } | string | number
  status: 'running' | 'completed' | 'failed'
  result?: {
    success?: boolean
    has_infringement?: boolean
    overall_recommendation?: string
    cost_usd?: number
    ip_count?: number
  }
  error_message?: string
  matched_ips?: string[]
}

export default function VisionAnalyzerPage() {
  const { canStartScans, user } = usePermissions()
  const [isScanning, setIsScanning] = useState(false)
  const [batchSize, setBatchSize] = useState(10)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [notification, setNotification] = useState<{type: 'success' | 'error', message: string} | null>(null)
  const [showProgressNotification, setShowProgressNotification] = useState(false)

  // Analysis detail modal
  const [selectedScan, setSelectedScan] = useState<{scan: ScanHistory, video: any} | null>(null)
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)

  // Scan history with infinite scroll (cursor-based)
  const [scans, setScans] = useState<ScanHistory[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [hasMoreHistory, setHasMoreHistory] = useState(true)
  const [statusFilter, setStatusFilter] = useState<'all' | 'running' | 'completed' | 'failed'>('all')
  const observerTarget = useRef<HTMLDivElement>(null)
  const limit = 20

  // Fetch real-time data
  const { data: budgetStats } = useSWR(
    'vision-budget',
    () => visionAPI.getBudgetStats(),
    { refreshInterval: 30000 }
  )

  const { data: analytics } = useSWR(
    'vision-analytics',
    () => visionAPI.getAnalytics(),
    { refreshInterval: 15000 }
  )

  // State for processing videos (fetched with scan history)
  const [processingVideos, setProcessingVideos] = useState<any[]>([])

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({type, message})
    setTimeout(() => setNotification(null), 4000)
  }

  // Load scan history WITH processing videos (cursor-based pagination)
  const loadHistory = useCallback(async (cursor: string | null = null, isRefresh: boolean = false) => {
    if (historyLoading) return

    setHistoryLoading(true)
    try {
      // CURSOR-BASED PAGINATION - FAST!
      const url = cursor
        ? `/api/channels/scan-history-with-processing?limit=${limit}&cursor=${cursor}`
        : `/api/channels/scan-history-with-processing?limit=${limit}`

      const response = await fetch(url)
      const data = await response.json()

      if (data.scan_history?.scans && data.scan_history.scans.length > 0) {
        if (isRefresh) {
          // On refresh, merge with existing scans to preserve scroll position
          // Update existing scans and add new ones at the top
          setScans(prev => {
            const newScans = data.scan_history.scans
            const existingIds = new Set(prev.map(s => s.scan_id))
            const trulyNew = newScans.filter(s => !existingIds.has(s.scan_id))

            // Update status of existing scans
            const updated = prev.map(scan => {
              const fresh = newScans.find(s => s.scan_id === scan.scan_id)
              return fresh || scan
            })

            // Add new scans at the top
            return [...trulyNew, ...updated]
          })
        } else {
          // Initial load or pagination
          setScans(prev => cursor === null ? data.scan_history.scans : [...prev, ...data.scan_history.scans])
        }
        setNextCursor(data.scan_history.next_cursor)
        setHasMoreHistory(data.scan_history.has_more || false)
      } else {
        setHasMoreHistory(false)
      }

      // Update processing videos (only on first page / refresh)
      if (cursor === null && data.processing_videos) {
        setProcessingVideos(data.processing_videos)
      }
    } catch (err) {
      console.error('Failed to load scan history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }, [historyLoading, limit])

  // Initial load
  useEffect(() => {
    loadHistory(null, false)
  }, [])

  // SSE connection for real-time updates (no more auto-refresh!)
  useEffect(() => {
    const eventSource = new EventSource('/api/channels/scan-updates-stream')

    eventSource.addEventListener('connected', () => {
      console.log('[SSE] Connected to scan updates stream')
    })

    eventSource.addEventListener('scan_updated', (event) => {
      const scan = JSON.parse(event.data)
      // Update existing scan or add new one
      setScans(prev => {
        const existingIndex = prev.findIndex(s => s.scan_id === scan.scan_id)
        if (existingIndex >= 0) {
          // Update existing scan
          const updated = [...prev]
          updated[existingIndex] = { ...updated[existingIndex], ...scan }
          return updated
        } else {
          // Add new scan at the top (only if status filter matches)
          if (statusFilter === 'all' || scan.status === statusFilter) {
            return [scan, ...prev]
          }
          return prev
        }
      })
    })

    eventSource.addEventListener('scan_completed', (event) => {
      const scan = JSON.parse(event.data)
      // Update scan status to completed
      setScans(prev => {
        const existingIndex = prev.findIndex(s => s.scan_id === scan.scan_id)
        if (existingIndex >= 0) {
          const updated = [...prev]
          updated[existingIndex] = { ...updated[existingIndex], ...scan, status: 'completed' }
          return updated
        } else {
          // Add completed scan at top if not exists
          if (statusFilter === 'all' || statusFilter === 'completed') {
            return [scan, ...prev]
          }
          return prev
        }
      })
    })

    eventSource.addEventListener('scan_failed', (event) => {
      const scan = JSON.parse(event.data)
      // Update scan status to failed
      setScans(prev => {
        const existingIndex = prev.findIndex(s => s.scan_id === scan.scan_id)
        if (existingIndex >= 0) {
          const updated = [...prev]
          updated[existingIndex] = { ...updated[existingIndex], ...scan, status: 'failed' }
          return updated
        } else {
          // Add failed scan at top if not exists
          if (statusFilter === 'all' || statusFilter === 'failed') {
            return [scan, ...prev]
          }
          return prev
        }
      })
    })

    eventSource.addEventListener('processing_videos', (event) => {
      const videos = JSON.parse(event.data)
      setProcessingVideos(videos)
    })

    eventSource.addEventListener('heartbeat', () => {
      // Keep-alive, no action needed
    })

    eventSource.addEventListener('error', (event) => {
      console.error('[SSE] Error:', event)
    })

    eventSource.onerror = () => {
      console.error('[SSE] Connection error, will reconnect...')
      // EventSource automatically reconnects
    }

    return () => {
      console.log('[SSE] Disconnecting from scan updates stream')
      eventSource.close()
    }
  }, [statusFilter])

  // Auto-fetch more pages when filter results in too few visible items
  useEffect(() => {
    const filteredScans = scans.filter(scan => statusFilter === 'all' || scan.status === statusFilter)
    const minVisible = 10 // Minimum number of visible items we want

    // If we have a filter active, fewer than minVisible items, and more data available
    if (statusFilter !== 'all' && filteredScans.length < minVisible && hasMoreHistory && !historyLoading && nextCursor) {
      console.log(`[Auto-fetch] Filter "${statusFilter}" shows only ${filteredScans.length} items, fetching more...`)
      loadHistory(nextCursor)
    }
  }, [scans, statusFilter, hasMoreHistory, historyLoading, nextCursor, loadHistory])

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasMoreHistory && !historyLoading && nextCursor) {
          loadHistory(nextCursor)
        }
      },
      { threshold: 0.1 }
    )

    const currentTarget = observerTarget.current
    if (currentTarget) {
      observer.observe(currentTarget)
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget)
      }
    }
  }, [hasMoreHistory, historyLoading, nextCursor, loadHistory])

  const formatDate = (timestamp: { seconds: number } | string | number) => {
    let date: Date
    if (typeof timestamp === 'string') {
      // ISO string format from API
      date = new Date(timestamp)
    } else if (typeof timestamp === 'number') {
      // Unix timestamp
      date = new Date(timestamp * 1000)
    } else if (timestamp && typeof timestamp === 'object' && 'seconds' in timestamp) {
      // Firestore timestamp format
      date = new Date(timestamp.seconds * 1000)
    } else {
      return 'Unknown'
    }
    return date.toLocaleString()
  }

  const getTypeLabel = (type: string) => {
    if (type === 'video_single') return '🎬 Video Scan'
    return type
  }

  const getStatusColor = (status: string) => {
    if (status === 'completed') return 'text-green-600'
    if (status === 'failed') return 'text-red-600'
    return 'text-blue-600'
  }

  const handleScanClick = async (scan: ScanHistory) => {
    if (scan.status !== 'completed') return

    setLoadingAnalysis(true)

    // Fetch analysis data
    try {
      const video = await videosAPI.getVideo(scan.video_id)
      if (video.vision_analysis) {
        // Open modal with analysis
        setSelectedScan({scan, video})
        setAnalysisModalOpen(true)
      } else {
        showNotification('error', 'Analysis data not found for this video')
      }
    } catch (error) {
      console.error('Failed to fetch analysis:', error)
      showNotification('error', 'Failed to load analysis details')
    } finally {
      setLoadingAnalysis(false)
    }
  }

  const handleBatchScan = async () => {
    setIsScanning(true)
    setShowConfirmDialog(false)
    try {
      await visionAPI.startBatchScan(batchSize)
      // No notifications needed - user is already on the Vision page viewing scan history
    } catch (error) {
      showNotification('error', `Failed to start batch scan: ${(error as Error).message}`)
    } finally {
      setIsScanning(false)
    }
  }

  // Calculate metrics
  const dailyBudget = budgetStats?.daily_budget_eur || 240
  const budgetUsed = budgetStats?.budget_used_eur || 0
  const totalAnalyzed = analytics?.total_analyzed || 0
  const totalErrors = analytics?.total_errors || 0
  const successRate = analytics?.success_rate || 0
  const infringementsFound = analytics?.infringements_found || 0
  const detectionRate = analytics?.detection_rate || 0
  const avgProcessingTime = analytics?.avg_processing_time_seconds || 0
  const videosPending = analytics?.videos_pending || 0

  return (
    <div className="space-y-6">
      {/* Page Header with Batch Controls */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 rounded-lg shadow-md p-6 border-2 border-blue-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Vision Analyzer Dashboard</h2>
            <p className="text-gray-600">Gemini 2.5 Flash video analysis with budget optimization</p>
          </div>
          <Link
            to="/"
            className="px-4 py-2 text-blue-600 hover:text-blue-800 font-medium"
          >
            ← Back to Overview
          </Link>
        </div>

        {/* Batch Scan Controls - Prominent */}
        <div className="flex items-center gap-6 bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex-1">
            <label htmlFor="batchSize" className="block text-sm font-medium text-gray-700 mb-2">
              Batch Size
            </label>
            <input
              id="batchSize"
              type="number"
              min="1"
              max="100"
              value={batchSize}
              onChange={(e) => setBatchSize(parseInt(e.target.value) || 10)}
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={isScanning || !canStartScans}
            />
            <p className="text-xs text-gray-500 mt-1">
              Number of videos to analyze (1-100)
            </p>
          </div>
          <div className="flex flex-col gap-2">
            {!canStartScans ? (
              <>
                <button
                  disabled
                  className="px-8 py-4 rounded-lg font-bold text-lg text-white bg-gray-400 cursor-not-allowed opacity-60"
                  title={`${user?.role} role cannot start scans`}
                >
                  ▶ Start Batch Scan
                </button>
                <p className="text-xs text-center text-gray-500">
                  {user?.role === 'legal' ? 'Legal' : 'Read-only'} access - Editor or Admin role required
                </p>
              </>
            ) : (
              <>
                <button
                  onClick={() => setShowConfirmDialog(true)}
                  disabled={isScanning}
                  className={`px-8 py-4 rounded-lg font-bold text-lg text-white transition-all active:scale-95 ${
                    isScanning
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-green-600 hover:bg-green-700 shadow-lg hover:shadow-xl'
                  }`}
                >
                  {isScanning ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Starting...
                    </span>
                  ) : '▶ Start Batch Scan'}
                </button>
                <p className="text-xs text-center text-gray-500">
                  {videosPending.toLocaleString()} videos pending
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Videos Analyzed</p>
              <p className="text-3xl font-bold text-blue-600 mt-2">
                {totalAnalyzed.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">Total scanned</p>
            </div>
            <span className="text-4xl">🔍</span>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Infringements Found</p>
              <p className="text-3xl font-bold text-red-600 mt-2">
                {infringementsFound.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">{detectionRate.toFixed(1)}% of analyzed</p>
            </div>
            <span className="text-4xl">⚠️</span>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Budget Used</p>
              <p className="text-3xl font-bold text-orange-600 mt-2">
                €{budgetUsed.toFixed(2)}
              </p>
              <p className="text-xs text-gray-500 mt-1">of €{dailyBudget.toFixed(2)} daily</p>
            </div>
            <span className="text-4xl">💰</span>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Success Rate</p>
              <p className="text-3xl font-bold text-green-600 mt-2">
                {successRate.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 mt-1">{totalErrors} errors</p>
            </div>
            <span className="text-4xl">✅</span>
          </div>
        </div>
      </div>

      {/* Scan History Section with Infinite Scroll */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-bold text-gray-900">Scan History</h3>
            <p className="text-gray-600 text-sm">
              {scans.filter(s => s.status === 'running').length} running, {scans.filter(s => s.status === 'failed').length} failed, {scans.filter(s => s.status === 'completed').length} completed
            </p>
          </div>
          <div className="flex items-center gap-4">
            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">Filter:</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="all">All Scans</option>
                <option value="running">Running</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                Live updates via SSE
              </div>
            </div>
          </div>
        </div>

        {scans.length === 0 && !historyLoading ? (
          <div className="text-center py-12">
            <span className="text-6xl">📊</span>
            <p className="text-gray-500 mt-4">No scan history yet</p>
            <p className="text-sm text-gray-400 mt-1">Start a batch scan to see results here</p>
          </div>
        ) : scans.filter(scan => statusFilter === 'all' || scan.status === statusFilter).length === 0 ? (
          <div className="text-center py-12">
            <span className="text-6xl">🔍</span>
            <p className="text-gray-500 mt-4">No {statusFilter} scans found</p>
            <p className="text-sm text-gray-400 mt-1">Try a different filter</p>
          </div>
        ) : (
          <div className="max-h-[600px] overflow-y-auto space-y-3 pr-2">
            {/* Queued/Processing Videos */}
            {processingVideos && processingVideos.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-bold text-purple-600 mb-2 flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Queue & Processing ({processingVideos.length})
                </h4>
                <div className="space-y-2">
                  {processingVideos.slice(0, 10).map((video: any) => {
                    const isProcessing = video.status === 'processing';
                    const borderColor = isProcessing ? 'border-purple-500' : 'border-orange-500';
                    const bgColor = isProcessing ? 'bg-purple-50' : 'bg-orange-50';
                    const textColor = isProcessing ? 'text-purple-900' : 'text-orange-900';
                    const badgeBg = isProcessing ? 'bg-purple-200' : 'bg-orange-200';
                    const statusColor = isProcessing ? 'text-purple-600' : 'text-orange-600';
                    const statusText = isProcessing ? 'Analyzing...' : 'Queued';

                    return (
                      <div
                        key={video.video_id}
                        className={`border-2 ${borderColor} ${bgColor} rounded-lg p-4`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <span className="text-sm font-medium">🎬 Video</span>
                            <a
                              href={`https://youtube.com/watch?v=${video.video_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={`text-xs px-2 py-1 rounded-full ${badgeBg} ${textColor} hover:opacity-80 truncate font-medium max-w-xs`}
                              title={video.title}
                            >
                              {video.title}
                            </a>
                          </div>
                          <span className={`text-sm font-bold ${statusColor} flex items-center gap-1 flex-shrink-0`}>
                            {isProcessing && (
                              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                            )}
                            {statusText}
                          </span>
                        </div>
                        <div className={`text-xs ${isProcessing ? 'text-purple-700' : 'text-orange-700'} flex justify-between items-center`}>
                          <span>{video.channel_title}</span>
                          {video.matched_ips && video.matched_ips.length > 0 && (
                            <span className={`px-2 py-0.5 ${badgeBg} rounded-full`}>
                              {video.matched_ips[0]}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {processingVideos.length > 5 && (
                    <div className="text-xs text-gray-500 text-center py-2">
                      + {processingVideos.length - 5} more videos queued
                    </div>
                  )}
                </div>
              </div>
            )}


            {/* All Scans (filtered by status) */}
            {scans.filter(scan => statusFilter === 'all' || scan.status === statusFilter).map((scan) => (
              <div
                key={scan.scan_id}
                onClick={() => handleScanClick(scan)}
                className={`border border-gray-200 rounded-lg p-4 transition-colors ${
                  scan.status === 'completed'
                    ? 'cursor-pointer hover:bg-gray-50 hover:border-blue-300'
                    : 'cursor-default hover:bg-gray-50'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-sm font-medium">{getTypeLabel(scan.scan_type)}</span>
                    <a
                      href={`https://youtube.com/watch?v=${scan.video_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-xs px-2 py-1 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-700 max-w-xs truncate"
                      title={scan.video_title}
                    >
                      {scan.video_title}
                    </a>
                  </div>
                  <div className="flex items-center gap-2">
                    {scan.status === 'completed' && (
                      <span className="text-xs text-blue-500">Click for details →</span>
                    )}
                    <span className={`text-sm font-medium ${getStatusColor(scan.status)}`}>
                      {scan.status === 'completed' && '✓ Complete'}
                      {scan.status === 'failed' && '✗ Failed'}
                      {scan.status === 'running' && (
                        <span className="flex items-center gap-1">
                          <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Running
                        </span>
                      )}
                    </span>
                  </div>
                </div>

                <div className="text-xs text-gray-500 mb-2">
                  <div>{scan.channel_title}</div>
                  <div>Started: {formatDate(scan.started_at)}
                  {scan.completed_at && ` • Completed: ${formatDate(scan.completed_at)}`}</div>
                </div>

                {scan.status === 'completed' && scan.result && (
                  <div className="flex gap-4 text-xs text-gray-600 flex-wrap items-center">
                    {scan.result.has_infringement !== undefined && (
                      <span className={`px-2 py-1 rounded-full font-medium ${
                        scan.result.has_infringement
                          ? 'bg-red-100 text-red-700'
                          : 'bg-green-100 text-green-700'
                      }`}>
                        {scan.result.has_infringement ? '⚠️ Infringement' : '✅ Clear'}
                      </span>
                    )}
                    {scan.result.overall_recommendation && (
                      <span className="px-2 py-1 bg-gray-100 rounded-full">
                        {scan.result.overall_recommendation}
                      </span>
                    )}
                    {scan.result.cost_usd !== undefined && (
                      <span>Cost: <strong>${scan.result.cost_usd.toFixed(4)}</strong></span>
                    )}
                    {scan.result.ip_count !== undefined && (
                      <span>{scan.result.ip_count} IP{scan.result.ip_count !== 1 ? 's' : ''}</span>
                    )}
                  </div>
                )}

                {scan.status === 'failed' && scan.error_message && (
                  <div className="text-xs text-red-600 mt-2 bg-red-50 p-2 rounded">
                    Error: {scan.error_message}
                  </div>
                )}
              </div>
            ))}

            {/* Infinite scroll trigger */}
            <div ref={observerTarget} className="py-4">
              {historyLoading && (
                <div className="flex items-center justify-center gap-2 text-gray-500">
                  <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Loading more...
                </div>
              )}
              {!hasMoreHistory && scans.length > 0 && (
                <p className="text-center text-gray-400 text-sm">No more scan history</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Processing Statistics */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4">📊 Processing Statistics</h3>
        <div className="space-y-4">
          <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
            <span className="text-sm font-medium text-gray-700">Avg Processing Time</span>
            <span className="text-lg font-bold text-blue-600">
              {avgProcessingTime.toFixed(1)}s
            </span>
          </div>
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
            <span className="text-sm font-medium text-gray-700">Videos Pending</span>
            <span className="text-lg font-bold text-gray-900">
              {videosPending.toLocaleString()}
            </span>
          </div>
          {analytics?.last_24h && (
            <>
              <div className="pt-3 border-t">
                <p className="text-sm font-semibold text-gray-600 mb-3">Last 24 Hours</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-center p-3 bg-blue-50 rounded-lg">
                    <p className="text-xs text-gray-600">Analyzed</p>
                    <p className="text-2xl font-bold text-blue-600">
                      {analytics.last_24h.analyzed}
                    </p>
                  </div>
                  <div className="text-center p-3 bg-orange-50 rounded-lg">
                    <p className="text-xs text-gray-600">Cost</p>
                    <p className="text-2xl font-bold text-orange-600">
                      ${analytics.last_24h.cost_usd.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
          {analytics?.by_status && (
            <div className="pt-3 border-t">
              <p className="text-sm font-semibold text-gray-600 mb-3">Status Breakdown</p>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex justify-between p-2 bg-green-50 rounded">
                  <span className="text-gray-600">✅ Success</span>
                  <span className="font-bold text-green-600">{analytics.by_status.success}</span>
                </div>
                <div className="flex justify-between p-2 bg-red-50 rounded">
                  <span className="text-gray-600">❌ Error</span>
                  <span className="font-bold text-red-600">{analytics.by_status.error}</span>
                </div>
                <div className="flex justify-between p-2 bg-yellow-50 rounded">
                  <span className="text-gray-600">⏳ Processing</span>
                  <span className="font-bold text-yellow-600">{analytics.by_status.processing}</span>
                </div>
                <div className="flex justify-between p-2 bg-gray-50 rounded">
                  <span className="text-gray-600">⏸️ Pending</span>
                  <span className="font-bold text-gray-600">{analytics.by_status.pending}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Budget Visualization */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4">💰 Daily Budget Tracking</h3>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-gray-600">
                €{budgetUsed.toFixed(2)} / €{dailyBudget} (${(budgetUsed * 1.08).toFixed(2)} USD)
              </span>
              <span className="font-medium">{((budgetUsed / dailyBudget) * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-4">
              <div
                className={`h-4 rounded-full transition-all ${
                  (budgetUsed / dailyBudget) > 0.9
                    ? 'bg-red-600'
                    : (budgetUsed / dailyBudget) > 0.7
                    ? 'bg-orange-600'
                    : 'bg-green-600'
                }`}
                style={{ width: `${Math.min((budgetUsed / dailyBudget) * 100, 100)}%` }}
              />
            </div>
          </div>
          <div className="grid grid-cols-4 gap-4 pt-3 text-sm">
            <div className="text-center p-3 bg-blue-50 rounded-lg">
              <p className="text-gray-600">Remaining</p>
              <p className="text-xl font-bold text-blue-600">
                €{(dailyBudget - budgetUsed).toFixed(2)}
              </p>
            </div>
            <div className="text-center p-3 bg-blue-50 rounded-lg">
              <p className="text-gray-600">Total Requests</p>
              <p className="text-xl font-bold text-blue-600">
                {budgetStats?.total_requests?.toLocaleString() || 0}
              </p>
            </div>
            <div className="text-center p-3 bg-blue-50 rounded-lg">
              <p className="text-gray-600">Avg Cost/Video</p>
              <p className="text-xl font-bold text-blue-600">
                ${budgetStats && budgetStats.total_requests > 0
                  ? (budgetStats.estimated_cost_usd / budgetStats.total_requests).toFixed(3)
                  : '0.000'}
              </p>
            </div>
            <div className="text-center p-3 bg-blue-50 rounded-lg">
              <p className="text-gray-600">Status</p>
              <p className={`text-xl font-bold ${
                (budgetUsed / dailyBudget) > 0.9 ? 'text-red-600' :
                (budgetUsed / dailyBudget) > 0.7 ? 'text-orange-600' : 'text-green-600'
              }`}>
                {(budgetUsed / dailyBudget) > 0.9 ? 'Critical' :
                 (budgetUsed / dailyBudget) > 0.7 ? 'High' : 'Normal'}
              </p>
            </div>
          </div>
          {budgetStats && (
            <div className="mt-3 pt-3 border-t text-xs text-gray-500 text-center">
              Input tokens: {budgetStats.total_input_tokens.toLocaleString()} •
              Output tokens: {budgetStats.total_output_tokens.toLocaleString()} •
              Updated {budgetStats.cache_age_seconds}s ago
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex space-x-4">
        <Link
          to="/videos"
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
        >
          → View Analyzed Videos
        </Link>
        <Link
          to="/risk"
          className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
        >
          → View Risk Analysis
        </Link>
      </div>

      {/* Notification Toast */}
      {notification && (
        <div className="fixed bottom-4 right-4 z-50 animate-slide-in">
          <div className={`rounded-lg shadow-lg p-4 ${
            notification.type === 'success'
              ? 'bg-green-600 text-white'
              : 'bg-red-600 text-white'
          }`}>
            <div className="flex items-center gap-3">
              {notification.type === 'success' ? (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              <span className="font-medium">{notification.message}</span>
            </div>
          </div>
        </div>
      )}

      {/* Scan Progress Notification */}
      <ScanProgressNotification
        show={showProgressNotification}
        onClose={() => setShowProgressNotification(false)}
      />

      {/* Analysis Detail Modal */}
      {selectedScan && analysisModalOpen && selectedScan.video.vision_analysis && (
        <AnalysisDetailModal
          isOpen={analysisModalOpen}
          onClose={() => {
            setAnalysisModalOpen(false)
            setSelectedScan(null)
          }}
          analysis={selectedScan.video.vision_analysis}
          videoId={selectedScan.scan.video_id}
          videoTitle={selectedScan.scan.video_title}
          channelId={selectedScan.scan.channel_id}
          channelTitle={selectedScan.scan.channel_title}
        />
      )}

      {/* Confirm Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowConfirmDialog(false)}>
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-900 mb-2">Confirm Batch Scan</h3>
            <p className="text-gray-600 mb-6">
              Start analyzing <span className="font-bold text-green-600">{batchSize}</span> videos
              with highest priority?
            </p>
            <div className="p-3 bg-blue-50 rounded-lg mb-4">
              <p className="text-sm text-blue-900">
                <span className="font-semibold">Estimated cost:</span> $
                {(batchSize * 0.008).toFixed(2)} - $
                {(batchSize * 0.012).toFixed(2)}
              </p>
              <p className="text-xs text-blue-700 mt-1">
                Budget remaining: €{(dailyBudget - budgetUsed).toFixed(2)}
              </p>
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirmDialog(false)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-all active:scale-95"
              >
                Cancel
              </button>
              <button
                onClick={handleBatchScan}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-all active:scale-95"
              >
                Start Scan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
