import GaugeChart from 'react-gauge-chart'
import type { PerformanceMetrics } from '../api/analytics'

interface PerformanceGaugesProps {
  metrics: PerformanceMetrics
}

interface GaugeCardProps {
  title: string
  value: number
  target: number
  score: number
  status: string
  unit?: string
}

function GaugeCard({ title, value, target, score, status, unit = '' }: GaugeCardProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'excellent':
        return '#3b82f6' // blue (changed from green)
      case 'good':
        return '#06b6d4' // cyan
      case 'fair':
        return '#f59e0b' // yellow
      case 'low':
        return '#ef4444' // red
      default:
        return '#6b7280' // gray
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'excellent':
        return '✓' // checkmark (changed from green circle)
      case 'good':
        return '↗' // up-right arrow
      case 'fair':
        return '⚠️' // warning
      case 'low':
      case 'warning':
        return '⚠️'
      default:
        return '○'
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h4 className="text-sm font-semibold text-gray-700 mb-4 text-center">{title}</h4>

      <div className="flex justify-center">
        <div style={{ width: '200px' }}>
          <GaugeChart
            id={`gauge-${title.replace(/\s/g, '-')}`}
            nrOfLevels={20}
            percent={score / 100}
            colors={['#ef4444', '#f59e0b', '#3b82f6']}
            arcWidth={0.3}
            hideText={false}
            textColor="#111827"
            needleColor="#6b7280"
            needleBaseColor="#6b7280"
            animDelay={0}
          />
        </div>
      </div>

      <div className="text-center mt-2">
        <p className="text-2xl font-bold text-gray-900">
          {value.toLocaleString()}{unit}
        </p>
        <p className="text-xs text-gray-600 mt-1">
          Target: {target}{unit}
        </p>
        <div className="flex items-center justify-center space-x-2 mt-2">
          <span className="text-xl">{getStatusIcon(status)}</span>
          <span className="text-sm font-medium capitalize" style={{ color: getStatusColor(status) }}>
            {status}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function PerformanceGauges({ metrics }: PerformanceGaugesProps) {
  return (
    <div>
      <h3 className="text-lg font-semibold text-gray-900 mb-4">System Performance</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <GaugeCard
          title="Discovery Efficiency"
          value={metrics.discovery_efficiency.value}
          target={metrics.discovery_efficiency.target}
          score={metrics.discovery_efficiency.score}
          status={metrics.discovery_efficiency.status}
          unit=" vid/unit"
        />

        <GaugeCard
          title="Analysis Throughput"
          value={metrics.analysis_throughput.value}
          target={metrics.analysis_throughput.target}
          score={metrics.analysis_throughput.score}
          status={metrics.analysis_throughput.status}
          unit=" vid/hr"
        />

        <GaugeCard
          title="Budget Utilization"
          value={metrics.budget_utilization.score}
          target={90}
          score={metrics.budget_utilization.score}
          status={metrics.budget_utilization.status}
          unit="%"
        />

        <GaugeCard
          title="Queue Health"
          value={metrics.queue_health.pending}
          target={metrics.queue_health.threshold}
          score={metrics.queue_health.score}
          status={metrics.queue_health.status}
          unit=" videos"
        />
      </div>
    </div>
  )
}
