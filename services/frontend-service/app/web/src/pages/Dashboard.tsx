import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { statusAPI } from '../api/status'
import { analyticsAPI } from '../api/analytics'
import SystemHealthBanner from '../components/SystemHealthBanner'
import MetricsGrid from '../components/MetricsGrid'
import ActivityTimeline from '../components/ActivityTimeline'
import AlertCenter from '../components/AlertCenter'
import RecentActivityFeed from '../components/RecentActivityFeed'
import PerformanceGauges from '../components/PerformanceGauges'
export default function Dashboard() {
  const [lastUpdated, setLastUpdated] = useState(new Date())

  // Fetch services with SWR (auto-refresh every 30 seconds)
  const { data: services, error: servicesError } = useSWR(
    'services',
    () => statusAPI.getServices(),
    { refreshInterval: 30000 }
  )

  // Fetch summary
  const { data: summary, error: summaryError } = useSWR(
    'summary',
    () => statusAPI.getSummary(),
    { refreshInterval: 30000 }
  )

  // Fetch analytics data
  const { data: hourlyStats } = useSWR(
    'hourly-stats',
    () => analyticsAPI.getHourlyStats(24),
    { refreshInterval: 30000 }
  )

  const { data: systemHealth } = useSWR(
    'system-health',
    () => analyticsAPI.getSystemHealth(),
    { refreshInterval: 30000 }
  )

  const { data: performanceMetrics } = useSWR(
    'performance-metrics',
    () => analyticsAPI.getPerformanceMetrics(),
    { refreshInterval: 30000 }
  )

  const { data: recentEvents } = useSWR(
    'recent-events',
    () => analyticsAPI.getRecentEvents(20),
    { refreshInterval: 30000 }
  )

  // Update last updated time whenever data changes
  useEffect(() => {
    if (services || summary || hourlyStats) {
      setLastUpdated(new Date())
    }
  }, [services, summary, hourlyStats])

  const loading = !services || !summary
  const error = servicesError || summaryError

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error.message || 'Failed to load dashboard'}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 text-red-600 hover:text-red-800 underline"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Dashboard Content */}
      <div className="space-y-6">
            {/* Page Header */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900">System Overview</h2>
              <p className="text-gray-600">
                Real-time monitoring and analytics
                <span className="ml-2 text-xs text-gray-400">
                  Auto-refreshes every 30 seconds
                </span>
              </p>
            </div>

            {/* System Health Banner */}
            <SystemHealthBanner services={services || []} lastUpdated={lastUpdated} />

            {/* Alert Center */}
            {systemHealth && (
              <AlertCenter
                alerts={systemHealth.alerts}
                warnings={systemHealth.warnings}
                info={systemHealth.info}
              />
            )}

            {/* Key Metrics Grid */}
            {summary && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Key Metrics (24h)</h3>
                <MetricsGrid summary={summary} metrics={performanceMetrics} />
              </div>
            )}

            {/* Activity Timeline */}
            {hourlyStats && hourlyStats.hours && hourlyStats.hours.length > 0 && (
              <ActivityTimeline data={hourlyStats.hours} />
            )}

            {/* Performance Gauges */}
            {performanceMetrics && (
              <PerformanceGauges metrics={performanceMetrics} />
            )}

            {/* Two-Column Layout: Last Run + Recent Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Last Discovery Run */}
              {summary?.last_run && (
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    Last Discovery Run
                  </h3>
                  <div className="space-y-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-sm text-gray-600">Completed</p>
                        <p className="text-lg font-medium text-gray-900">
                          {new Date(summary.last_run.timestamp).toLocaleString()}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-600">Duration</p>
                        <p className="text-lg font-medium text-gray-900">
                          {summary.last_run.duration_seconds.toFixed(1)}s
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 pt-4 border-t">
                      <div>
                        <p className="text-xs text-gray-600">Videos</p>
                        <p className="text-xl font-bold text-blue-600">
                          {summary.last_run.videos_discovered.toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600">Quota</p>
                        <p className="text-xl font-bold text-gray-900">
                          {summary.last_run.quota_used.toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600">Channels</p>
                        <p className="text-xl font-bold text-gray-900">
                          {summary.last_run.channels_tracked.toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Recent Activity Feed */}
              {recentEvents && (
                <RecentActivityFeed events={recentEvents.events} />
              )}
            </div>

          </div>
    </div>
  )
}
