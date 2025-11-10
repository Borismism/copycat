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
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [viewMode, setViewMode] = useState<'hourly' | 'daily'>('hourly')

  // Format selected date for API (YYYY-MM-DD in UTC)
  const startDateParam = selectedDate.toISOString().split('T')[0]
  const now = new Date()
  const isToday = selectedDate.toDateString() === now.toDateString()
  const isSameMonth = selectedDate.getMonth() === now.getMonth() &&
                      selectedDate.getFullYear() === now.getFullYear()

  // For monthly view, format as first day of month
  const monthStartParam = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1).toISOString().split('T')[0]

  // Fetch services with SWR (auto-refresh every 30 seconds)
  const { data: services, error: servicesError } = useSWR(
    'services',
    () => statusAPI.getServices(),
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,  // Don't refetch on tab focus/refresh
      dedupingInterval: 5000  // Cache for 5 seconds
    }
  )

  // Fetch summary
  const { data: summary, error: summaryError } = useSWR(
    'summary',
    () => statusAPI.getSummary(),
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,
      dedupingInterval: 5000
    }
  )

  // Fetch analytics data with date selection (hourly)
  const { data: hourlyStats, mutate: mutateHourlyStats } = useSWR(
    viewMode === 'hourly' ? ['hourly-stats', startDateParam] : null,  // Only fetch when in hourly mode
    () => analyticsAPI.getHourlyStats(24, isToday ? undefined : startDateParam),
    {
      refreshInterval: isToday ? 30000 : 0,  // Only auto-refresh for today
      revalidateOnFocus: false,
      dedupingInterval: 5000,
      keepPreviousData: true  // Keep showing old data while loading new data
    }
  )

  // Fetch daily stats for monthly view
  const { data: dailyStats, mutate: mutateDailyStats } = useSWR(
    viewMode === 'daily' ? ['daily-stats', monthStartParam] : null,  // Only fetch when in daily mode
    () => {
      // For current month, don't pass start_date (let backend handle it)
      // For other months, pass the 1st of that month
      return analyticsAPI.getDailyStats(30, isSameMonth ? undefined : monthStartParam)
    },
    {
      refreshInterval: isSameMonth ? 30000 : 0,  // Only auto-refresh for current month
      revalidateOnFocus: false,
      dedupingInterval: 5000,
      keepPreviousData: true
    }
  )

  const { data: systemHealth } = useSWR(
    'system-health',
    () => analyticsAPI.getSystemHealth(),
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,
      dedupingInterval: 5000
    }
  )

  const { data: performanceMetrics } = useSWR(
    'performance-metrics',
    () => analyticsAPI.getPerformanceMetrics(),
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,
      dedupingInterval: 5000
    }
  )

  const { data: recentEvents } = useSWR(
    'recent-events',
    () => analyticsAPI.getRecentEvents(20),
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,
      dedupingInterval: 5000
    }
  )

  // Update last updated time whenever data changes
  useEffect(() => {
    if (services || summary || hourlyStats || dailyStats) {
      setLastUpdated(new Date())
    }
  }, [services, summary, hourlyStats, dailyStats])

  // Refetch stats when selected date or view mode changes
  useEffect(() => {
    if (viewMode === 'hourly') {
      mutateHourlyStats()
    } else {
      mutateDailyStats()
    }
  }, [selectedDate, viewMode, mutateHourlyStats, mutateDailyStats])

  // DON'T BLOCK - only block on critical data (summary)
  const loading = !summary
  const error = summaryError

  // Skeleton loader component
  const SkeletonCard = ({ className = '' }: { className?: string }) => (
    <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
      <div className="animate-pulse space-y-4">
        <div className="h-6 bg-gray-200 rounded w-1/3"></div>
        <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
      </div>
    </div>
  )

  const MetricsGridSkeleton = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="bg-white rounded-lg shadow-md p-6">
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
            <div className="h-8 bg-gray-200 rounded w-3/4"></div>
            <div className="h-3 bg-gray-200 rounded w-full"></div>
          </div>
        </div>
      ))}
    </div>
  )

  const ActivityTimelineSkeleton = () => (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="animate-pulse space-y-4">
        <div className="h-6 bg-gray-200 rounded w-1/3"></div>
        <div className="h-64 bg-gray-200 rounded"></div>
      </div>
    </div>
  )

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
            {!services ? (
              <SkeletonCard />
            ) : (
              <SystemHealthBanner services={services} lastUpdated={lastUpdated} />
            )}

            {/* Key Metrics Grid */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Key Metrics (24h)</h3>
              {loading ? (
                <MetricsGridSkeleton />
              ) : (
                <MetricsGrid summary={summary} metrics={performanceMetrics} />
              )}
            </div>

            {/* Activity Timeline with Date Selector */}
            <div>
              {loading ? (
                <ActivityTimelineSkeleton />
              ) : (viewMode === 'hourly' && hourlyStats?.hours) || (viewMode === 'daily' && dailyStats?.days) ? (
                <div className="bg-white rounded-lg shadow-md p-6">
                  {/* View Mode Toggle & Navigation */}
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">Activity Timeline</h3>
                      <p className="text-sm text-gray-600">
                        {viewMode === 'hourly' ? (
                          isToday ? 'Last 24 Hours' : selectedDate.toLocaleDateString()
                        ) : (
                          isSameMonth ? 'This Month' : selectedDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      {/* View Mode Toggle */}
                      <div className="flex bg-gray-100 rounded-lg p-1">
                        <button
                          onClick={() => setViewMode('hourly')}
                          className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                            viewMode === 'hourly'
                              ? 'bg-white text-blue-600 shadow-sm'
                              : 'text-gray-600 hover:text-gray-900'
                          }`}
                        >
                          24 Hours
                        </button>
                        <button
                          onClick={() => setViewMode('daily')}
                          className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                            viewMode === 'daily'
                              ? 'bg-white text-blue-600 shadow-sm'
                              : 'text-gray-600 hover:text-gray-900'
                          }`}
                        >
                          Month
                        </button>
                      </div>

                      {/* Date Navigation */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            if (viewMode === 'hourly') {
                              setSelectedDate(new Date(selectedDate.getTime() - 24 * 60 * 60 * 1000))
                            } else {
                              // Previous month
                              const newDate = new Date(selectedDate)
                              newDate.setMonth(newDate.getMonth() - 1)
                              setSelectedDate(newDate)
                            }
                          }}
                          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                          title={viewMode === 'hourly' ? 'Previous day' : 'Previous month'}
                        >
                          <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                          </svg>
                        </button>
                        <button
                          onClick={() => setSelectedDate(new Date())}
                          className="px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          disabled={viewMode === 'hourly' ? isToday : isSameMonth}
                        >
                          {viewMode === 'hourly' ? 'Today' : 'This Month'}
                        </button>
                        <button
                          onClick={() => {
                            if (viewMode === 'hourly') {
                              setSelectedDate(new Date(selectedDate.getTime() + 24 * 60 * 60 * 1000))
                            } else {
                              // Next month
                              const newDate = new Date(selectedDate)
                              newDate.setMonth(newDate.getMonth() + 1)
                              setSelectedDate(newDate)
                            }
                          }}
                          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                          title={viewMode === 'hourly' ? 'Next day' : 'Next month'}
                          disabled={viewMode === 'hourly' ? isToday : isSameMonth}
                        >
                          <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                  <ActivityTimeline
                    data={viewMode === 'hourly' ? hourlyStats!.hours : dailyStats!.days}
                    viewMode={viewMode}
                  />
                </div>
              ) : null}
            </div>

            {/* Performance Gauges */}
            {!loading && performanceMetrics && (
              <PerformanceGauges metrics={performanceMetrics} />
            )}

            {/* Two-Column Layout: Last Run + Recent Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Last Discovery Run */}
              {loading ? (
                <SkeletonCard />
              ) : (
                summary?.last_run && (
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
                )
              )}

              {/* Recent Activity Feed */}
              {loading ? (
                <SkeletonCard />
              ) : (
                recentEvents && (
                  <RecentActivityFeed events={recentEvents.events} />
                )
              )}
            </div>

          </div>
    </div>
  )
}
