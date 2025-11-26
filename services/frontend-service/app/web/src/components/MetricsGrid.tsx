import type { SystemSummary } from '../types'
import type { PerformanceMetrics } from '../api/analytics'
import { usePermissions } from '../hooks/usePermissions'

interface MetricsGridProps {
  summary: SystemSummary
  metrics?: PerformanceMetrics
  timeRange?: string
}

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  trend?: {
    direction: 'up' | 'down' | 'flat'
    value: string
  }
  icon?: string
  color?: string
}

function MetricCard({ title, value, subtitle, trend, icon, color = 'bg-white' }: MetricCardProps) {
  const trendColors = {
    up: 'text-blue-600',  // Changed from green to blue
    down: 'text-red-600',
    flat: 'text-gray-600',
  }

  const trendIcons = {
    up: '↑',
    down: '↓',
    flat: '→',
  }

  return (
    <div className={`${color} rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-gray-900">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {trend && (
            <p className={`text-sm mt-2 font-medium ${trendColors[trend.direction]}`}>
              {trendIcons[trend.direction]} {trend.value}
            </p>
          )}
          {subtitle && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        {icon && (
          <span className="text-4xl ml-4">{icon}</span>
        )}
      </div>
    </div>
  )
}

export default function MetricsGrid({ summary, metrics, timeRange = '24h' }: MetricsGridProps) {
  const { canViewCosts, canViewQuota, canViewAdminMetrics, isClient } = usePermissions()

  // Get time range label for subtitles
  const getTimeRangeLabel = () => {
    switch (timeRange) {
      case '24h': return 'Last 24 hours'
      case '7d': return 'Last 7 days'
      case '30d': return 'Last 30 days'
      case '1y': return 'Last year'
      case 'this_year': return 'This year'
      case 'all_time': return 'All time'
      default: return 'Last 24 hours'
    }
  }

  // Calculate time range in hours for throughput calculation
  const getTimeRangeHours = () => {
    switch (timeRange) {
      case '24h': return 24
      case '7d': return 24 * 7
      case '30d': return 24 * 30
      case '1y': return 24 * 365
      case 'this_year':
        const now = new Date()
        const startOfYear = new Date(now.getFullYear(), 0, 1)
        return Math.floor((now.getTime() - startOfYear.getTime()) / (1000 * 60 * 60))
      case 'all_time': return 24 * 365 * 10 // Assume 10 years max
      default: return 24
    }
  }

  // Calculate efficiency
  const efficiency = summary.quota_used > 0
    ? (summary.videos_discovered / summary.quota_used).toFixed(2)
    : '0.00'

  // Calculate throughput
  const timeRangeHours = getTimeRangeHours()
  const throughput = summary.videos_analyzed > 0
    ? (summary.videos_analyzed / timeRangeHours).toFixed(1)
    : '0.0'

  // For clients, use a 3-column grid. For admins, use 4-column grid
  const gridClass = isClient
    ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
    : "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"

  return (
    <div className={gridClass}>
      {/* Row 1: Discovery & Channel Tracking */}
      <MetricCard
        title="Videos Discovered"
        value={summary.videos_discovered}
        subtitle={getTimeRangeLabel()}
        icon="🔍"
        trend={
          summary.videos_discovered > 2000
            ? { direction: 'up', value: 'High activity' }
            : { direction: 'flat', value: 'Normal' }
        }
      />

      <MetricCard
        title="Channels Tracked"
        value={summary.channels_tracked}
        subtitle="Total active channels"
        icon="📺"
      />

      {canViewQuota && (
        <MetricCard
          title="YouTube Quota"
          value={`${summary.quota_used.toLocaleString()} / ${summary.quota_total.toLocaleString()}`}
          subtitle={`${((summary.quota_used / summary.quota_total) * 100).toFixed(1)}% utilized`}
          icon="📊"
          color={
            summary.quota_used / summary.quota_total > 0.9
              ? 'bg-red-50'
              : summary.quota_used / summary.quota_total > 0.75
              ? 'bg-yellow-50'
              : 'bg-white'
          }
        />
      )}

      {canViewAdminMetrics && (
        <MetricCard
          title="Discovery Efficiency"
          value={`${efficiency} vid/unit`}
          subtitle={`Target: >0.5 ${parseFloat(efficiency) >= 0.5 ? '✓' : '⚠️'}`}
          icon="⚡"
          trend={
            parseFloat(efficiency) >= 0.5
              ? { direction: 'up', value: 'Excellent' }
              : { direction: 'down', value: 'Below target' }
          }
        />
      )}

      {/* Row 2: Vision Analysis & Budget */}
      <MetricCard
        title="Videos Analyzed"
        value={summary.videos_analyzed}
        subtitle={getTimeRangeLabel()}
        icon="🤖"
      />

      <MetricCard
        title="Infringements Found"
        value={summary.infringements_found}
        subtitle={
          summary.videos_analyzed > 0
            ? `${((summary.infringements_found / summary.videos_analyzed) * 100).toFixed(1)}% detection rate`
            : 'No data yet'
        }
        icon="⚠️"
        color={summary.infringements_found > 0 ? 'bg-red-50' : 'bg-white'}
      />

      {canViewCosts && (
        <MetricCard
          title="Gemini Budget"
          value={metrics?.budget_utilization ? `€${metrics.budget_utilization.spent} / €${metrics.budget_utilization.total}` : 'N/A'}
          subtitle={
            metrics?.budget_utilization
              ? `${metrics.budget_utilization.score.toFixed(1)}% utilized`
              : 'Vision analyzer not active'
          }
          icon="💰"
          color={
            metrics?.budget_utilization && metrics.budget_utilization.score > 90
              ? 'bg-yellow-50'
              : 'bg-white'
          }
        />
      )}

      {canViewAdminMetrics && (
        <MetricCard
          title="Analysis Throughput"
          value={`${throughput} vid/hr`}
          subtitle={`Target: >20 ${parseFloat(throughput) >= 20 ? '✓' : '⚠️'}`}
          icon="🚀"
          trend={
            parseFloat(throughput) >= 20
              ? { direction: 'up', value: 'On target' }
              : { direction: 'flat', value: 'Below target' }
          }
        />
      )}
    </div>
  )
}
