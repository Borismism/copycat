import { useState, useEffect, useCallback, useRef } from 'react'
import useSWR from 'swr'
import { Link } from 'react-router-dom'
import { discoveryAPI } from '../api/discovery'
import { statusAPI } from '../api/status'
import type { QuotaStatus } from '../types'
import { useAuth } from '../contexts/AuthContext'

export default function DiscoveryPage() {
  const { user } = useAuth()
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [maxQuotaInput, setMaxQuotaInput] = useState<string>('1000')

  // Discovery history state
  const [history, setHistory] = useState<any[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [hasMoreHistory, setHasMoreHistory] = useState(true)
  const [selectedRun, setSelectedRun] = useState<any | null>(null)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [historyOffset, setHistoryOffset] = useState(0)
  const observerTarget = useRef<HTMLDivElement | null>(null)
  const historyLimit = 20

  // Fetch summary data for dashboard metrics
  const { data: summary } = useSWR(
    'summary',
    () => statusAPI.getSummary(),
    { refreshInterval: 30000 }
  )

  // Fetch quota with auto-refresh (every 30 seconds)
  const { data: quota, isLoading: quotaLoading } = useSWR(
    'discovery-quota',
    () => discoveryAPI.getQuota(),
    { refreshInterval: 30000 }
  )

  // Load discovery history
  const loadHistory = useCallback(async (offset: number = 0, isRefresh: boolean = false) => {
    if (historyLoading) return
    setHistoryLoading(true)
    try {
      const response = await fetch(`/api/discovery/history?limit=${historyLimit}&offset=${offset}`)
      const data = await response.json()
      if (data.runs && data.runs.length > 0) {
        setHistory(prev => {
          if (offset === 0) {
            // For refresh: only update if we haven't scrolled (preserves pagination)
            if (isRefresh && prev.length > historyLimit) {
              // Update only the first page, keep the rest
              return [...data.runs, ...prev.slice(historyLimit)]
            }
            // For initial load: replace all and reset offset
            setHistoryOffset(historyLimit)
            return data.runs
          }
          // For pagination: append
          return [...prev, ...data.runs]
        })
        setHasMoreHistory(data.runs.length === historyLimit)
        if (offset > 0) {
          setHistoryOffset(offset + historyLimit)
        }
      } else {
        setHasMoreHistory(false)
      }
    } catch (err) {
      console.error('Failed to load discovery history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }, [historyLimit])  // Remove historyLoading from deps

  // Initial history load and auto-refresh
  useEffect(() => {
    loadHistory(0, false)
    const interval = setInterval(() => loadHistory(0, true), 10000)
    return () => clearInterval(interval)
  }, [])  // Empty deps - only run once on mount

  // Infinite scroll observer for history
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasMoreHistory && !historyLoading) {
          console.log('[IntersectionObserver] Loading more history, offset:', historyOffset)
          loadHistory(historyOffset, false)
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
  }, [hasMoreHistory, historyLoading, historyOffset])  // Remove loadHistory to prevent re-creating observer

  const loadQuota = async () => {
    try {
      setQuotaLoading(true)
      const quotaData = await discoveryAPI.getQuota()
      setQuota(quotaData)
    } catch (err) {
      console.error('Failed to load quota:', err)
    } finally {
      setQuotaLoading(false)
    }
  }

  const triggerDiscovery = async () => {
    // Validate quota input
    if (!maxQuotaInput || maxQuotaInput.trim() === '') {
      setError('Please enter a quota limit')
      return
    }

    const quotaValue = Number(maxQuotaInput)
    if (isNaN(quotaValue) || quotaValue <= 0) {
      setError('Please enter a valid quota limit (must be greater than 0)')
      return
    }

    try {
      setRunning(true)
      setError(null)

      // Use state flags that persist across event handlers
      const state = {
        isComplete: false,
        hasReceivedData: false,
        completionTimer: null as number | null,
      }

      // Use SSE for real-time progress through frontend proxy
      const eventSource = new EventSource(
        `/api/discovery/trigger/stream?max_quota=${quotaValue}`
      )

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[SSE]', data)
          state.hasReceivedData = true // We got data!

          if (data.status === 'complete') {
            // Mark complete IMMEDIATELY to prevent error logging
            state.isComplete = true
            console.log('[SSE] Complete! Data:', data)

            // Reload quota to show updated usage
            loadQuota()

            // Reload history to show the new run
            loadHistory(0, false)

            // Close after a brief delay to ensure message is processed
            state.completionTimer = setTimeout(() => {
              eventSource.close()
            }, 100)

            // Stop running state
            setTimeout(() => {
              setRunning(false)
            }, 500)
          } else if (data.status === 'error') {
            state.isComplete = true
            setError(data.message)

            state.completionTimer = setTimeout(() => {
              eventSource.close()
            }, 100)

            setTimeout(() => setRunning(false), 500)
          }
        } catch (err) {
          console.error('[SSE] Failed to parse event:', err)
          setError(`Failed to parse SSE message: ${err}`)
        }
      }

      eventSource.onerror = () => {
        console.log('[SSE] onerror fired. hasReceivedData:', state.hasReceivedData, 'isComplete:', state.isComplete)
        // SSE connections naturally close when the server finishes streaming
        // Only treat as error if we never received any data
        if (!state.hasReceivedData && !state.isComplete) {
          console.error('[SSE] Failed to connect to discovery service')
          setError('Failed to connect to discovery service - check if backend is running')
          setTimeout(() => setRunning(false), 2000)
        } else {
          console.log('[SSE] Connection closed normally (stream complete)')
        }
        // Otherwise, connection closing is normal (server finished streaming)

        // Clean up
        if (state.completionTimer) {
          clearTimeout(state.completionTimer)
        }
        eventSource.close()
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMsg)
      setRunning(false)
    }
  }

  // Calculate efficiency metrics
  const efficiency = summary && summary.quota_used > 0
    ? (summary.videos_discovered / summary.quota_used).toFixed(2)
    : '0.00'

  return (
    <div className="space-y-6">
      {/* Page Header with Trigger Controls */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 rounded-lg shadow-md p-6 border-2 border-blue-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Discovery Service Dashboard</h2>
            <p className="text-gray-600">YouTube video discovery and channel tracking</p>
          </div>
          <Link
            to="/"
            className="px-4 py-2 text-blue-600 hover:text-blue-800 font-medium"
          >
            ← Back to Overview
          </Link>
        </div>

        {/* Discovery Trigger Controls - Prominent */}
        <div className="flex items-center gap-6 bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex-1">
            <label htmlFor="quotaLimit" className="block text-sm font-medium text-gray-700 mb-2">
              Max Quota Limit
            </label>
            <input
              id="quotaLimit"
              type="number"
              min="100"
              max="10000"
              value={maxQuotaInput}
              onChange={(e) => setMaxQuotaInput(e.target.value)}
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={running || (user?.role === 'read' || user?.role === 'legal')}
              placeholder="Enter quota limit"
            />
            <p className="text-xs text-gray-500 mt-1">
              YouTube API units to use (100-10,000)
            </p>
            {maxQuotaInput && Number(maxQuotaInput) < 400 && Number(maxQuotaInput) > 0 && (
              <p className="text-xs text-yellow-600 mt-1">
                💡 Use 400+ quota for keyword searches
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            {user && (user.role === 'read' || user.role === 'legal') ? (
              <>
                <button
                  disabled
                  className="px-8 py-4 rounded-lg font-bold text-lg text-white bg-gray-400 cursor-not-allowed opacity-60"
                  title={`${user.role} role cannot trigger discovery runs`}
                >
                  ▶ Start Discovery Run
                </button>
                <p className="text-xs text-center text-gray-500">
                  {user.role === 'legal' ? 'Legal' : 'Read-only'} access - Editor or Admin role required
                </p>
              </>
            ) : (
              <button
                onClick={triggerDiscovery}
                disabled={running}
                className={`px-8 py-4 rounded-lg font-bold text-lg text-white transition-all active:scale-95 ${
                  running
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-700 shadow-lg hover:shadow-xl'
                }`}
              >
                {running ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Running...
                  </span>
                ) : '▶ Start Discovery Run'}
              </button>
            )}
            {quota && user && user.role !== 'read' && user.role !== 'legal' && (
              <p className="text-xs text-center text-gray-500">
                {quota.remaining_quota.toLocaleString()} quota remaining
              </p>
            )}
          </div>
        </div>

        {/* Error Display */}
        {error && !running && (
          <div className="mt-4 p-4 bg-red-50 border-2 border-red-300 rounded-lg">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">❌</span>
              <div className="flex-1">
                <p className="text-sm font-bold text-red-900">Error</p>
                <p className="text-sm text-red-700">{error}</p>
              </div>
              <button
                onClick={() => setError(null)}
                className="text-red-400 hover:text-red-600"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Key Metrics Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Videos Discovered</p>
                <p className="text-3xl font-bold text-blue-600 mt-2">
                  {summary.videos_discovered.toLocaleString()}
                </p>
                <p className="text-xs text-gray-500 mt-1">Last 24 hours</p>
              </div>
              <span className="text-4xl">🔍</span>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Channels Tracked</p>
                <p className="text-3xl font-bold text-purple-600 mt-2">
                  {summary.channels_tracked.toLocaleString()}
                </p>
                <p className="text-xs text-gray-500 mt-1">Active channels</p>
              </div>
              <span className="text-4xl">📺</span>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Discovery Efficiency</p>
                <p className="text-3xl font-bold text-cyan-600 mt-2">
                  {efficiency}
                </p>
                <p className="text-xs text-gray-500 mt-1">videos per quota unit</p>
              </div>
              <span className="text-4xl">⚡</span>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Quota Utilization</p>
                <p className="text-3xl font-bold text-orange-600 mt-2">
                  {((summary.quota_used / summary.quota_total) * 100).toFixed(0)}%
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {summary.quota_used.toLocaleString()} / {summary.quota_total.toLocaleString()}
                </p>
              </div>
              <span className="text-4xl">📊</span>
            </div>
          </div>
        </div>
      )}

      {/* YouTube API Quota */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4">YouTube API Quota</h3>
        {quotaLoading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="grid grid-cols-4 gap-4 pt-3">
              <div className="h-20 bg-gray-100 rounded-lg"></div>
              <div className="h-20 bg-gray-100 rounded-lg"></div>
              <div className="h-20 bg-gray-100 rounded-lg"></div>
              <div className="h-20 bg-gray-100 rounded-lg"></div>
            </div>
          </div>
        ) : quota ? (
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600">
                  {quota.used_quota.toLocaleString()} / {quota.daily_quota.toLocaleString()} units
                </span>
                <span className="font-medium">{(quota.utilization * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-4">
                <div
                  className={`h-4 rounded-full transition-all ${
                    quota.utilization > 0.9
                      ? 'bg-red-600'
                      : quota.utilization > 0.7
                      ? 'bg-yellow-600'
                      : 'bg-blue-600'
                  }`}
                  style={{ width: `${Math.min(quota.utilization * 100, 100)}%` }}
                />
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 text-sm pt-3">
              <div className="text-center p-3 bg-blue-50 rounded-lg">
                <p className="text-gray-600">Remaining</p>
                <p className="text-xl font-bold text-blue-600">
                  {quota.remaining_quota.toLocaleString()}
                </p>
              </div>
              <div className="text-center p-3 bg-orange-50 rounded-lg">
                <p className="text-gray-600">Used</p>
                <p className="text-xl font-bold text-orange-600">
                  {quota.used_quota.toLocaleString()}
                </p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-gray-600">Total</p>
                <p className="text-xl font-bold text-gray-900">
                  {quota.daily_quota.toLocaleString()}
                </p>
              </div>
              <div className="text-center p-3 bg-blue-50 rounded-lg">
                <p className="text-gray-600">Status</p>
                <p className={`text-xl font-bold ${
                  quota.utilization > 0.9 ? 'text-red-600' :
                  quota.utilization > 0.7 ? 'text-orange-600' : 'text-green-600'
                }`}>
                  {quota.utilization > 0.9 ? 'Critical' :
                   quota.utilization > 0.7 ? 'High' : 'Normal'}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">Failed to load quota information</p>
        )}
      </div>

      {/* Last Discovery Run Details */}
      {summary?.last_run && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Last Discovery Run</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Completed</p>
              <p className="text-sm font-medium">
                {new Date(summary.last_run.timestamp).toLocaleString()}
              </p>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Duration</p>
              <p className="text-2xl font-bold text-gray-900">
                {summary.last_run.duration_seconds.toFixed(1)}s
              </p>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Videos</p>
              <p className="text-2xl font-bold text-blue-600">
                {summary.last_run.videos_discovered}
              </p>
            </div>
            <div className="text-center p-4 bg-purple-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Channels</p>
              <p className="text-2xl font-bold text-purple-600">
                {summary.last_run.channels_tracked}
              </p>
            </div>
            <div className="text-center p-4 bg-orange-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Quota Used</p>
              <p className="text-2xl font-bold text-orange-600">
                {summary.last_run.quota_used}
              </p>
            </div>
          </div>
        </div>
      )}


      {/* Discovery History Section */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-bold text-gray-900">Discovery History</h3>
            <p className="text-gray-600 text-sm">
              {history.filter(r => r.status === 'running').length} running
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              Auto-updating every 10s
            </div>
          </div>
        </div>

        {history.length === 0 && !historyLoading ? (
          <div className="text-center py-12">
            <span className="text-6xl">🔍</span>
            <p className="text-gray-500 mt-4">No discovery runs yet</p>
            <p className="text-sm text-gray-400 mt-1">Start a discovery job to see results here</p>
          </div>
        ) : (
          <div className="max-h-[600px] overflow-y-auto space-y-3 pr-2">
            {/* Currently Running Discoveries - Real-time */}
            {history.filter(r => r.status === 'running').length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-bold text-purple-600 mb-2 flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Currently Running ({history.filter(r => r.status === 'running').length})
                </h4>
                <div className="space-y-2">
                  {history.filter(r => r.status === 'running').map((run) => {
                    const formatDate = (date: any) => {
                      if (!date) return 'N/A'
                      const d = date.seconds ? new Date(date.seconds * 1000) : new Date(date)
                      return d.toLocaleString()
                    }

                    return (
                      <div
                        key={run.run_id}
                        className="border-2 border-purple-500 bg-purple-50 rounded-lg p-4"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <span className="text-sm font-medium">🔍 Discovery Run</span>
                          </div>
                          <span className="text-sm font-bold text-purple-600 flex items-center gap-1 flex-shrink-0">
                            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Running...
                          </span>
                        </div>
                        <div className="text-xs text-purple-700">
                          Started: {formatDate(run.started_at)}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* All Discoveries - exclude running ones (they're shown above) */}
            {history.filter(r => r.status !== 'running').map((run) => {
              const formatDate = (date: any) => {
                if (!date) return 'N/A'
                const d = date.seconds ? new Date(date.seconds * 1000) : new Date(date)
                return d.toLocaleString()
              }

              const duration = run.duration_seconds
                ? `${Math.floor(run.duration_seconds / 60)}m ${Math.floor(run.duration_seconds % 60)}s`
                : 'N/A'

              return (
                <div
                  key={run.run_id}
                  onClick={() => {
                    if (run.status === 'completed') {
                      setSelectedRun(run)
                      setShowDetailModal(true)
                    }
                  }}
                  className={`border border-gray-200 rounded-lg p-4 transition-colors ${
                    run.status === 'completed'
                      ? 'cursor-pointer hover:bg-gray-50 hover:border-blue-300'
                      : 'cursor-default hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-sm font-medium">🔍 Discovery Run</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {run.status === 'completed' && (
                        <span className="text-xs text-blue-500">Click for details →</span>
                      )}
                      <span className={`text-sm font-medium ${
                        run.status === 'completed' ? 'text-green-600' :
                        run.status === 'failed' ? 'text-red-600' :
                        'text-blue-600'
                      }`}>
                        {run.status === 'completed' && '✓ Complete'}
                        {run.status === 'failed' && '✗ Failed'}
                        {run.status === 'running' && (
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
                    <div>Started: {formatDate(run.started_at)}
                    {run.completed_at && ` • Completed: ${formatDate(run.completed_at)}`}</div>
                  </div>

                  {run.status === 'completed' && (
                    <div className="flex gap-4 text-xs text-gray-600 flex-wrap items-center">
                      <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full font-medium">
                        {run.videos_discovered || 0} videos
                      </span>
                      <span className="px-2 py-1 bg-green-100 text-green-700 rounded-full font-medium">
                        {run.videos_with_ip_match || 0} IP matches
                      </span>
                      <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full font-medium">
                        {run.quota_used || 0} quota
                      </span>
                      <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full font-medium">
                        {duration}
                      </span>
                    </div>
                  )}

                  {run.status === 'failed' && run.error_message && (
                    <div className="text-xs text-red-600 mt-2 bg-red-50 p-2 rounded">
                      Error: {run.error_message}
                    </div>
                  )}
                </div>
              )
            })}

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
              {!hasMoreHistory && history.length > 0 && (
                <p className="text-center text-gray-400 text-sm">No more discovery runs</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Detail Modal - Beautiful Results View */}
      {selectedRun && showDetailModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowDetailModal(false)}>
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="bg-gradient-to-r from-blue-50 to-green-50 border-b-2 border-blue-300 p-6">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-2xl font-bold text-gray-900">🎯 Discovery Results</h2>
                <button onClick={() => setShowDetailModal(false)} className="text-gray-500 hover:text-gray-700 text-2xl">
                  ✕
                </button>
              </div>
              <p className="text-sm text-gray-600">
                Started: {new Date((selectedRun.started_at?.seconds || Date.now() / 1000) * 1000).toLocaleString()}
              </p>
            </div>

            <div className="p-6 space-y-6">
              {/* Main Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-lg p-4 shadow border border-gray-200">
                  <p className="text-sm font-medium text-gray-600 mb-1">New Videos Found</p>
                  <p className="text-3xl font-bold text-blue-600">{selectedRun.videos_discovered?.toLocaleString() || 0}</p>
                  <p className="text-xs text-gray-500 mt-1">From all sources</p>
                </div>
                <div className="bg-white rounded-lg p-4 shadow border border-gray-200">
                  <p className="text-sm font-medium text-gray-600 mb-1">IP Matches</p>
                  <p className="text-3xl font-bold text-green-600">{selectedRun.videos_with_ip_match?.toLocaleString() || 0}</p>
                  <p className="text-xs text-gray-500 mt-1">Character matches</p>
                </div>
                <div className="bg-white rounded-lg p-4 shadow border border-gray-200">
                  <p className="text-sm font-medium text-gray-600 mb-1">Quota Used</p>
                  <p className="text-3xl font-bold text-orange-600">{selectedRun.quota_used?.toLocaleString() || 0}</p>
                  <p className="text-xs text-gray-500 mt-1">API units</p>
                </div>
                <div className="bg-white rounded-lg p-4 shadow border border-gray-200">
                  <p className="text-sm font-medium text-gray-600 mb-1">Duration</p>
                  <p className="text-3xl font-bold text-purple-600">{selectedRun.duration_seconds?.toFixed(1) || 0}s</p>
                  <p className="text-xs text-gray-500 mt-1">Time taken</p>
                </div>
              </div>

              {/* Discovery Breakdown */}
              <div className="space-y-4">
                {/* Channel Scans */}
                {selectedRun.all_query_details && selectedRun.all_query_details.some((q: any) => q.keyword?.startsWith('CHANNEL:')) && (
                  <div className="bg-white rounded-lg p-5 shadow border-l-4 border-purple-500">
                    <h4 className="text-lg font-bold mb-3 text-purple-900">📺 Channel Scans</h4>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {selectedRun.all_query_details
                        .filter((q: any) => q.keyword?.startsWith('CHANNEL:'))
                        .map((query: any, idx: number) => (
                          <div key={idx} className="p-3 bg-purple-50 rounded border border-purple-200">
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-sm text-purple-900">{query.keyword.replace('CHANNEL:', '')}</span>
                              <div className="flex gap-2 items-center">
                                <span className={`text-sm font-bold ${(query.new_count || 0) > 0 ? 'text-green-600' : 'text-gray-400'}`}>
                                  {query.new_count || 0} new
                                </span>
                                {query.rediscovered_count > 0 && (
                                  <span className="text-xs text-orange-600">({query.rediscovered_count} known)</span>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* YouTube Keyword Searches */}
                {selectedRun.all_query_details && selectedRun.all_query_details.some((q: any) => !q.keyword?.startsWith('CHANNEL:')) && (
                  <div className="bg-white rounded-lg p-5 shadow border-l-4 border-blue-500">
                    <h4 className="text-lg font-bold mb-3 text-blue-900">🔍 YouTube Keyword Searches</h4>
                    <div className="mb-3 flex gap-2 text-xs flex-wrap">
                      <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                        {selectedRun.all_query_details.filter((q: any) => !q.keyword?.startsWith('CHANNEL:')).length} queries
                      </span>
                      <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
                        {selectedRun.time_window || 'ALL TIME'}
                      </span>
                      <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded">
                        {selectedRun.orders_used?.join(', ') || 'various orders'}
                      </span>
                    </div>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {selectedRun.all_query_details
                        .filter((q: any) => !q.keyword?.startsWith('CHANNEL:'))
                        .map((query: any, idx: number) => (
                          <div key={idx} className="p-3 bg-blue-50 rounded border border-blue-200">
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-semibold text-blue-900">"{query.keyword}"</span>
                              <div className="flex gap-2 items-center">
                                {query.results_count > 0 && (
                                  <span className="text-xs text-gray-500">{query.results_count} from YouTube →</span>
                                )}
                                <span className={`text-sm font-bold ${(query.new_count || 0) > 0 ? 'text-green-600' : 'text-gray-400'}`}>
                                  {query.new_count || 0} new
                                </span>
                                {query.rediscovered_count > 0 && (
                                  <span className="text-xs text-orange-600">({query.rediscovered_count} known)</span>
                                )}
                              </div>
                            </div>
                            <div className="flex gap-2 text-xs">
                              <span className="text-gray-600">order: {query.order}</span>
                              <span className="text-gray-400">•</span>
                              <span className="text-gray-600">window: {query.time_window}</span>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex gap-4">
                <a
                  href="/videos"
                  className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-center"
                >
                  → View Videos
                </a>
                <a
                  href="/channels"
                  className="flex-1 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium text-center"
                >
                  → View Channels
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
