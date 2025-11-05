import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { Link } from 'react-router-dom'
import { discoveryAPI } from '../api/discovery'
import { statusAPI } from '../api/status'
import type { QuotaStatus, DiscoveryStats } from '../types'

export default function DiscoveryPage() {
  const [quota, setQuota] = useState<QuotaStatus | null>(null)
  const [lastRun, setLastRun] = useState<DiscoveryStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [maxQuota, setMaxQuota] = useState(1000)
  const [progress, setProgress] = useState<string>('')
  const [currentTier, setCurrentTier] = useState<number>(0)
  const [showResults, setShowResults] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch summary data for dashboard metrics
  const { data: summary } = useSWR(
    'summary',
    () => statusAPI.getSummary(),
    { refreshInterval: 30000 }
  )

  useEffect(() => {
    loadQuota()
  }, [])

  const loadQuota = async () => {
    try {
      setLoading(true)
      const quotaData = await discoveryAPI.getQuota()
      setQuota(quotaData)
    } catch (err) {
      console.error('Failed to load quota:', err)
    } finally {
      setLoading(false)
    }
  }

  const triggerDiscovery = async () => {
    try {
      setRunning(true)
      setProgress('Initializing discovery...')
      setCurrentTier(0)
      setError(null)
      setShowResults(false) // Hide old results

      // Use state flags that persist across event handlers
      const state = {
        isComplete: false,
        hasReceivedData: false,
        completionTimer: null as number | null,
      }

      // Use SSE for real-time progress through frontend proxy
      const eventSource = new EventSource(
        `/api/discovery/trigger/stream?max_quota=${maxQuota}`
      )

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[SSE]', data)
          state.hasReceivedData = true // We got data!

          if (data.status === 'starting') {
            setProgress(data.message || `Starting with ${data.quota} quota...`)
            setCurrentTier(1)
          } else if (data.status === 'searching') {
            setProgress(data.message || 'Searching YouTube...')
            setCurrentTier(2)
          } else if (data.status === 'complete') {
            // Mark complete IMMEDIATELY to prevent error logging
            state.isComplete = true
            console.log('[SSE] Complete! Data:', data)
            setProgress(data.message || `✅ Discovery Complete!`)
            setCurrentTier(3)
            setLastRun(data)
            setShowResults(true)
            console.log('[SSE] Results panel should show now')
            loadQuota()

            // Close after a brief delay to ensure message is processed
            state.completionTimer = setTimeout(() => {
              eventSource.close()
            }, 100)

            // Keep running state for results display
            setTimeout(() => {
              setRunning(false)
              setShowResults(true)
            }, 500)
          } else if (data.status === 'error') {
            state.isComplete = true
            setError(data.message)
            setProgress(`❌ Error: ${data.message}`)

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
          setProgress('❌ Connection error')
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
      setProgress(`Failed: ${errorMsg}`)
      setRunning(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading...</div>
  }

  // Calculate efficiency metrics
  const efficiency = summary && summary.quota_used > 0
    ? (summary.videos_discovered / summary.quota_used).toFixed(2)
    : '0.00'

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
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

      {/* Two-Column Layout: Control Panel + Quota */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Control Panel */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Control Panel</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Max Quota Limit
              </label>
              <input
                type="number"
                value={maxQuota}
                onChange={(e) => setMaxQuota(Number(e.target.value))}
                min={100}
                max={10000}
                step={100}
                disabled={running}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <span className="ml-2 text-sm text-gray-500">units</span>
              {maxQuota < 400 && (
                <p className="mt-1 text-xs text-yellow-600">
                  💡 Use 400+ quota for keyword searches (current: {maxQuota} too low for new discoveries)
                </p>
              )}
            </div>
            <button
              onClick={triggerDiscovery}
              disabled={running}
              className={`w-full px-6 py-3 rounded-lg font-medium ${
                running
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {running ? 'Running Discovery...' : '▶ Trigger Discovery Run'}
            </button>

            {/* Progress Display */}
            {running && (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className="animate-spin h-6 w-6 border-3 border-blue-600 border-t-transparent rounded-full"></div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-blue-900">{progress}</p>
                    {currentTier > 0 && (
                      <div className="mt-2 w-full bg-blue-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${(currentTier / 3) * 100}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

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
        </div>

        {/* YouTube API Quota */}
        {quota && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">YouTube API Quota</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-600">
                    {quota.used_quota.toLocaleString()} / {quota.daily_quota.toLocaleString()} units
                  </span>
                  <span className="font-medium">{(quota.utilization * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      quota.utilization > 0.9
                        ? 'bg-red-600'
                        : quota.utilization > 0.7
                        ? 'bg-yellow-600'
                        : 'bg-blue-600'
                    }`}
                    style={{ width: `${quota.utilization * 100}%` }}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm pt-3">
                <div>
                  <span className="text-gray-600">Remaining:</span>
                  <p className="font-medium text-lg mt-1">{quota.remaining_quota.toLocaleString()}</p>
                  <p className="text-xs text-gray-500">units available</p>
                </div>
                <div>
                  <span className="text-gray-600">Status:</span>
                  <p className={`font-medium text-lg mt-1 ${
                    quota.utilization > 0.9 ? 'text-red-600' :
                    quota.utilization > 0.7 ? 'text-yellow-600' : 'text-blue-600'
                  }`}>
                    {quota.utilization > 0.9 ? 'Critical' :
                     quota.utilization > 0.7 ? 'High' : 'Normal'}
                  </p>
                  <p className="text-xs text-gray-500">usage level</p>
                </div>
              </div>
            </div>
          </div>
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

      {/* Results Panel - BIG and OBVIOUS */}
      {showResults && lastRun && (
        <div className="bg-gradient-to-r from-blue-50 to-green-50 border-2 border-blue-300 rounded-lg shadow-lg p-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-2xl font-bold text-gray-900">🎯 Discovery Results</h3>
            <button
              onClick={() => setShowResults(false)}
              className="text-gray-400 hover:text-gray-600 text-xl"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg p-4 shadow">
              <p className="text-sm font-medium text-gray-600 mb-1">Videos Discovered</p>
              <p className="text-4xl font-bold text-blue-600">{lastRun.videos_discovered}</p>
              <p className="text-xs text-gray-500 mt-1">Total new videos found</p>
            </div>
            <div className="bg-white rounded-lg p-4 shadow">
              <p className="text-sm font-medium text-gray-600 mb-1">IP Matches</p>
              <p className="text-4xl font-bold text-green-600">{lastRun.videos_with_ip_match}</p>
              <p className="text-xs text-gray-500 mt-1">Videos with character matches</p>
            </div>
            <div className="bg-white rounded-lg p-4 shadow">
              <p className="text-sm font-medium text-gray-600 mb-1">Quota Used</p>
              <p className="text-4xl font-bold text-orange-600">{lastRun.quota_used}</p>
              <p className="text-xs text-gray-500 mt-1">YouTube API units consumed</p>
            </div>
            <div className="bg-white rounded-lg p-4 shadow">
              <p className="text-sm font-medium text-gray-600 mb-1">Channels</p>
              <p className="text-4xl font-bold text-purple-600">{lastRun.channels_tracked}</p>
              <p className="text-xs text-gray-500 mt-1">Channels discovered/updated</p>
            </div>
          </div>

          <div className="mt-6 flex space-x-4">
            <a
              href="/videos"
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
            >
              → View Videos
            </a>
            <a
              href="/channels"
              className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
            >
              → View Channels
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
