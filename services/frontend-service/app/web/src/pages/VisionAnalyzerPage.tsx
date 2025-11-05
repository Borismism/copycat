import { useState } from 'react'
import useSWR from 'swr'
import { Link } from 'react-router-dom'
import { visionAPI } from '../api/vision'

export default function VisionAnalyzerPage() {
  const [isScanning, setIsScanning] = useState(false)
  const [batchSize, setBatchSize] = useState(10)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [notification, setNotification] = useState<{type: 'success' | 'error', message: string} | null>(null)

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

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({type, message})
    setTimeout(() => setNotification(null), 4000)
  }

  const handleBatchScan = async () => {
    setIsScanning(true)
    setShowConfirmDialog(false)
    try {
      const result = await visionAPI.startBatchScan(batchSize)
      showNotification('success', `Batch scan started! ${result.videos_queued} videos queued.`)
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
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isScanning}
            />
            <p className="text-xs text-gray-500 mt-1">
              Number of videos to analyze (1-100)
            </p>
          </div>
          <div className="flex flex-col gap-2">
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
              <p className="text-xs text-gray-500 mt-1">of €{dailyBudget} daily</p>
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

      {/* Two-Column Layout: Stats + Errors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

        {/* Error Tracking */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center justify-between">
            <span>❌ Recent Errors</span>
            <span className="text-sm font-normal text-gray-500">
              {totalErrors} total
            </span>
          </h3>
          {analytics?.recent_errors && analytics.recent_errors.length > 0 ? (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {analytics.recent_errors.map((error, idx) => (
                <div key={idx} className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <div className="flex items-start justify-between mb-1">
                    <span className="text-xs font-mono text-red-900 font-semibold">
                      {error.video_id}
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(error.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-sm text-red-700">{error.error_message}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <span className="text-6xl">🎉</span>
              <p className="text-gray-500 mt-4">No recent errors!</p>
              <p className="text-sm text-gray-400 mt-1">System running smoothly</p>
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

      {/* Confirm Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50" onClick={() => setShowConfirmDialog(false)}>
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
