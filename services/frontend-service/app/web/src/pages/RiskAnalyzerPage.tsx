import useSWR from 'swr'
import { Link } from 'react-router-dom'
import { statusAPI } from '../api/status'

export default function RiskAnalyzerPage() {
  // Fetch summary data
  const { data: summary } = useSWR(
    'summary',
    () => statusAPI.getSummary(),
    { refreshInterval: 30000 }
  )

  // Calculate metrics from available data
  const totalVideos = summary?.videos_discovered || 0
  const videosAnalyzed = summary?.videos_analyzed || 0
  const infringementsFound = summary?.infringements_found || 0
  const avgRiskScore = videosAnalyzed > 0 ? (infringementsFound / videosAnalyzed) * 100 : 0

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Risk Analyzer Dashboard</h2>
          <p className="text-gray-600">Adaptive risk scoring and view velocity tracking</p>
        </div>
        <Link
          to="/"
          className="px-4 py-2 text-blue-600 hover:text-blue-800 font-medium"
        >
          ← Back to Overview
        </Link>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Videos Analyzed</p>
              <p className="text-3xl font-bold text-blue-600 mt-2">
                {totalVideos.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">Total in system</p>
            </div>
            <span className="text-4xl">📊</span>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Average Risk Score</p>
              <p className="text-3xl font-bold text-orange-600 mt-2">
                {avgRiskScore.toFixed(1)}
              </p>
              <p className="text-xs text-gray-500 mt-1">Out of 100</p>
            </div>
            <span className="text-4xl">⚠️</span>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Infringements Found</p>
              <p className="text-3xl font-bold text-red-600 mt-2">
                {infringementsFound.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">Confirmed violations</p>
            </div>
            <span className="text-4xl">🔴</span>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Videos Analyzed</p>
              <p className="text-3xl font-bold text-purple-600 mt-2">
                {videosAnalyzed.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">Scanned by Gemini</p>
            </div>
            <span className="text-4xl">⏱️</span>
          </div>
        </div>
      </div>


      {/* Quick Actions */}
      <div className="flex space-x-4">
        <Link
          to="/videos"
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
        >
          → View High Risk Videos
        </Link>
        <Link
          to="/channels"
          className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
        >
          → View Channel Reputation
        </Link>
      </div>
    </div>
  )
}
