import { formatDistanceToNow } from 'date-fns'
import type { Alert } from '../api/analytics'

interface AlertCenterProps {
  alerts: Alert[]
  warnings: Alert[]
  info: Alert[]
}

interface AlertCardProps {
  alert: Alert
  onDismiss?: (id: string) => void
}

function AlertCard({ alert, onDismiss }: AlertCardProps) {
  const getAlertColor = (type: string) => {
    switch (type) {
      case 'critical':
        return 'bg-red-50 border-red-300 text-red-900'
      case 'warning':
        return 'bg-yellow-50 border-yellow-300 text-yellow-900'
      case 'info':
        return 'bg-blue-50 border-blue-300 text-blue-900'
      default:
        return 'bg-gray-50 border-gray-300 text-gray-900'
    }
  }

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'critical':
        return '🔴'
      case 'warning':
        return '⚠️'
      case 'info':
        return 'ℹ️'
      default:
        return '📌'
    }
  }

  const timeAgo = formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })

  return (
    <div className={`rounded-lg border-2 p-4 ${getAlertColor(alert.type)}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3 flex-1">
          <span className="text-2xl">{getAlertIcon(alert.type)}</span>
          <div className="flex-1">
            <h4 className="font-bold text-sm mb-1">{alert.title}</h4>
            <p className="text-sm mb-2">{alert.message}</p>
            {alert.action && (
              <p className="text-xs font-medium">
                <span className="opacity-75">Action:</span> {alert.action}
              </p>
            )}
            <p className="text-xs opacity-50 mt-2">{timeAgo}</p>
          </div>
        </div>
        {onDismiss && (
          <button
            onClick={() => onDismiss(alert.id)}
            className="text-gray-400 hover:text-gray-600 ml-2"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}

export default function AlertCenter({ alerts, warnings, info }: AlertCenterProps) {
  const totalAlerts = alerts.length + warnings.length + info.length

  if (totalAlerts === 0) {
    return (
      <div className="bg-white border-2 border-gray-200 rounded-lg p-6 text-center">
        <span className="text-4xl text-gray-400">✓</span>
        <h3 className="text-lg font-semibold text-gray-700 mt-2">All Clear</h3>
        <p className="text-sm text-gray-500">No alerts or warnings at this time</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Alert Center</h3>
        <span className="text-sm text-gray-600">
          {totalAlerts} {totalAlerts === 1 ? 'alert' : 'alerts'}
        </span>
      </div>

      <div className="space-y-3">
        {/* Critical Alerts */}
        {alerts.map((alert) => (
          <AlertCard key={alert.id} alert={alert} />
        ))}

        {/* Warnings */}
        {warnings.map((warning) => (
          <AlertCard key={warning.id} alert={warning} />
        ))}

        {/* Info */}
        {info.map((infoItem) => (
          <AlertCard key={infoItem.id} alert={infoItem} />
        ))}
      </div>
    </div>
  )
}
