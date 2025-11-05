import { Link } from 'react-router-dom'
import type { ServiceHealth, ServiceStatus } from '../types'

interface SystemHealthBannerProps {
  services: ServiceHealth[]
  lastUpdated?: Date
}

const getServiceLink = (serviceName: string): string => {
  if (serviceName.includes('discovery')) return '/discovery'
  if (serviceName.includes('risk')) return '/risk'
  if (serviceName.includes('vision')) return '/vision'
  if (serviceName.includes('channel')) return '/channels'
  if (serviceName.includes('video')) return '/videos'
  return '/'
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

      {/* Service cards - centered and clean */}
      <div className="flex flex-wrap justify-center gap-3">
        {services.map((service) => {
          const link = getServiceLink(service.service_name)
          const serviceName = service.service_name.replace('-service', '')

          return (
            <Link
              key={service.service_name}
              to={link}
              className="group relative bg-white rounded-lg px-4 py-3 flex flex-col items-center min-w-[140px] hover:shadow-lg hover:scale-105 transition-all border border-gray-200"
            >
              <span className={`text-xl mb-1 ${getStatusColor(service.status)}`}>
                {getStatusIcon(service.status)}
              </span>
              <p className="text-sm font-medium text-gray-700 capitalize">
                {serviceName}
              </p>
              <p className={`text-xs mt-0.5 capitalize ${getStatusColor(service.status)}`}>
                {service.status}
              </p>
            </Link>
          )
        })}
      </div>

      {overall.status !== 'healthy' && (
        <div className="mt-4 p-3 bg-white bg-opacity-50 rounded">
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
