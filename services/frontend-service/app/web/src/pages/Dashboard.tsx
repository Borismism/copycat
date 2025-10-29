import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { statusAPI } from '../api/status'
import type { ServiceHealth, SystemSummary, ServiceStatus } from '../types'

export default function Dashboard() {
  const [services, setServices] = useState<ServiceHealth[]>([])
  const [summary, setSummary] = useState<SystemSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [servicesData, summaryData] = await Promise.all([
        statusAPI.getServices(),
        statusAPI.getSummary(),
      ])
      setServices(servicesData)
      setSummary(summaryData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: ServiceStatus) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 text-green-800'
      case 'degraded':
        return 'bg-yellow-100 text-yellow-800'
      case 'unhealthy':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusIcon = (status: ServiceStatus) => {
    switch (status) {
      case 'healthy':
        return '🟢'
      case 'degraded':
        return '🟡'
      case 'unhealthy':
        return '🔴'
      default:
        return '⚪'
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
        <button
          onClick={loadData}
          className="mt-2 text-red-600 hover:text-red-800 underline"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">System Overview</h2>
        <p className="text-gray-600">Monitor services and view 24-hour activity</p>
      </div>

      {/* Service Status Grid */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Service Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {services.map((service) => (
            <div key={service.service_name} className="bg-white rounded-lg shadow p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-2xl">{getStatusIcon(service.status)}</span>
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${getStatusColor(
                        service.status
                      )}`}
                    >
                      {service.status}
                    </span>
                  </div>
                  <h4 className="mt-2 font-medium text-gray-900 text-sm">
                    {service.service_name}
                  </h4>
                  {service.error && (
                    <p className="mt-1 text-xs text-red-600">{service.error}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 24-Hour Summary */}
      {summary && (
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            24-Hour Activity Summary
          </h3>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
              <div>
                <p className="text-sm text-gray-600">Videos Discovered</p>
                <p className="text-3xl font-bold text-gray-900">
                  {summary.videos_discovered.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Channels Tracked</p>
                <p className="text-3xl font-bold text-gray-900">
                  {summary.channels_tracked.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">YouTube Quota Used</p>
                <p className="text-3xl font-bold text-gray-900">
                  {summary.quota_used.toLocaleString()} / {summary.quota_total.toLocaleString()}
                </p>
                <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${(summary.quota_used / summary.quota_total) * 100}%` }}
                  />
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-600">Videos Analyzed</p>
                <p className="text-3xl font-bold text-gray-900">
                  {summary.videos_analyzed.toLocaleString()}
                </p>
                <p className="text-xs text-gray-500">Pending implementation</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Infringements Found</p>
                <p className="text-3xl font-bold text-red-600">
                  {summary.infringements_found.toLocaleString()}
                </p>
                <p className="text-xs text-gray-500">Pending implementation</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Last Discovery Run */}
      {summary?.last_run && (
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Last Discovery Run
          </h3>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start mb-4">
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
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-gray-600">Videos Found</p>
                <p className="text-2xl font-bold text-blue-600">
                  {summary.last_run.videos_discovered.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Quota Used</p>
                <p className="text-2xl font-bold text-gray-900">
                  {summary.last_run.quota_used.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Channels Scanned</p>
                <p className="text-2xl font-bold text-gray-900">
                  {summary.last_run.channels_tracked.toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
        <div className="flex space-x-4">
          <Link
            to="/discovery"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Trigger Discovery
          </Link>
          <Link
            to="/channels"
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
          >
            View Channels
          </Link>
          <Link
            to="/videos"
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
          >
            Browse Videos
          </Link>
        </div>
      </div>
    </div>
  )
}
