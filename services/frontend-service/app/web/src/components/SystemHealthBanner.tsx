import { Link } from 'react-router-dom'
import type { ServiceHealth, ServiceStatus } from '../types'

interface SystemHealthBannerProps {
  services: ServiceHealth[]
  lastUpdated?: Date
}

const getServiceLink = (serviceName: string): string => {
  if (serviceName.includes('discovery')) return '/dashboards/discovery'
  if (serviceName.includes('vision')) return '/dashboards/vision'
  return '/dashboards'
}

const getStatusIcon = (status: ServiceStatus) => {
  switch (status) {
    case 'healthy':
      return '●'  // Filled circle
    case 'degraded':
      return '●'  // Filled circle (yellow/orange)
    case 'unhealthy':
      return '●'  // Filled circle (red)
    default:
      return '○'  // Empty circle
  }
}

const getStatusColor = (status: ServiceStatus) => {
  switch (status) {
    case 'healthy':
      return 'text-blue-500'
    case 'degraded':
      return 'text-yellow-500'
    case 'unhealthy':
      return 'text-red-500'
    default:
      return 'text-gray-400'
  }
}

const getOverallStatus = (services: ServiceHealth[]) => {
  const hasUnhealthy = services.some(s => s.status === 'unhealthy')
  const hasDegraded = services.some(s => s.status === 'degraded')

  if (hasUnhealthy) return { status: 'unhealthy', text: 'Issues detected', icon: '●', iconColor: 'text-red-500', color: 'bg-red-50 border-red-200 text-red-900' }
  if (hasDegraded) return { status: 'degraded', text: 'Performance issues', icon: '●', iconColor: 'text-yellow-500', color: 'bg-yellow-50 border-yellow-200 text-yellow-900' }
  return { status: 'healthy', text: 'All systems operational', icon: '●', iconColor: 'text-blue-500', color: 'bg-white border-gray-200 text-gray-700' }
}

export default function SystemHealthBanner({ services, lastUpdated }: SystemHealthBannerProps) {
  const overall = getOverallStatus(services)
  const timeSince = lastUpdated
    ? Math.floor((Date.now() - lastUpdated.getTime()) / 1000)
    : 0

  return (
    <div className={`rounded-lg border p-6 ${overall.color}`}>
      {/* Compact header - single line */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-2">
          <span className={`text-lg ${overall.iconColor}`}>{overall.icon}</span>
          <span className="text-sm font-medium">{overall.text}</span>
        </div>
        <span className="text-xs text-gray-500">
          Updated {timeSince < 60 ? `${timeSince}s ago` : 'just now'}
        </span>
      </div>

      {/* Service cards - larger and more prominent */}
      <div className="flex flex-wrap justify-center gap-6">
        {services.map((service) => {
          const link = getServiceLink(service.service_name)
          const serviceName = service.service_name.replace('-service', '').replace('-', ' ')

          // Get service icon
          const serviceIcon = serviceName.includes('discovery') ? '🔍' : '🤖'

          return (
            <Link
              key={service.service_name}
              to={link}
              className="group relative bg-white rounded-xl px-8 py-6 flex flex-col items-center min-w-[200px] hover:shadow-xl hover:scale-105 transition-all border-2 border-gray-200 hover:border-blue-400"
            >
              {/* Service icon */}
              <div className="text-4xl mb-3">
                {serviceIcon}
              </div>

              {/* Service name */}
              <p className="text-lg font-semibold text-gray-900 capitalize mb-2">
                {serviceName}
              </p>

              {/* Status indicator */}
              <div className="flex items-center gap-2">
                <span className={`text-lg ${getStatusColor(service.status)}`}>
                  {getStatusIcon(service.status)}
                </span>
                <p className={`text-sm font-medium capitalize ${getStatusColor(service.status)}`}>
                  {service.status}
                </p>
              </div>

              {/* View details hint */}
              <p className="text-xs text-gray-400 mt-3 group-hover:text-blue-600 transition-colors">
                View details →
              </p>
            </Link>
          )
        })}
      </div>

      {overall.status !== 'healthy' && (
        <div className="mt-6 p-4 bg-white bg-opacity-50 rounded-lg">
          <p className="text-sm font-medium">
            {services.filter(s => s.status !== 'healthy').map(s => (
              <span key={s.service_name} className="block">
                {s.service_name}: {s.error || 'Service unavailable'}
              </span>
            ))}
          </p>
        </div>
      )}
    </div>
  )
}
