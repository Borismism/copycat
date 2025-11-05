import { formatDistanceToNow } from 'date-fns'
import { Link } from 'react-router-dom'
import type { Event } from '../api/analytics'

interface RecentActivityFeedProps {
  events: Event[]
}

export default function RecentActivityFeed({ events }: RecentActivityFeedProps) {
  if (events.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
        <p className="text-sm text-gray-500 text-center py-8">No recent activity</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Recent Activity
      </h3>

      <div className="space-y-3">
        {events.map((event) => (
          <div
            key={event.id}
            className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <span className="text-2xl flex-shrink-0">{event.icon}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">{event.title}</p>
              <p className="text-sm text-gray-600 mt-1">{event.message}</p>
              <p className="text-xs text-gray-400 mt-1">
                {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
              </p>
            </div>
            {event.video_id && (
              <Link
                to={`/videos?video_id=${event.video_id}`}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium flex-shrink-0"
              >
                View →
              </Link>
            )}
          </div>
        ))}
      </div>

      {events.length >= 20 && (
        <div className="mt-4 text-center">
          <button className="text-sm text-blue-600 hover:text-blue-800 font-medium">
            View all activity →
          </button>
        </div>
      )}
    </div>
  )
}
