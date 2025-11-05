import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { format, parseISO } from 'date-fns'
import type { HourlyStats } from '../api/analytics'

interface ActivityTimelineProps {
  data: HourlyStats[]
}

export default function ActivityTimeline({ data }: ActivityTimelineProps) {
  // Format data for display (convert UTC to local time)
  const chartData = data.map(item => {
    // Parse the ISO timestamp and convert to local time
    const utcDate = parseISO(item.timestamp)
    const localTime = format(utcDate, 'HH:mm')

    return {
      time: localTime,
      discoveries: item.discoveries,
      infringements: item.infringements,
    }
  })

  // Calculate totals
  const totalDiscoveries = data.reduce((sum, item) => sum + item.discoveries, 0)
  const totalInfringements = data.reduce((sum, item) => sum + item.infringements, 0)

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Activity Timeline (Last 24 Hours)
          </h3>
          <p className="text-sm text-gray-600">
            Total: {totalDiscoveries.toLocaleString()} videos discovered, {totalInfringements.toLocaleString()} infringements
          </p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 12 }}
            stroke="#6b7280"
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 12 }}
            stroke="#3b82f6"
            label={{ value: 'Videos Discovered', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 12 }}
            stroke="#ef4444"
            label={{ value: 'Infringements', angle: 90, position: 'insideRight', style: { fontSize: 12 } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '8px 12px',
            }}
          />
          <Legend />
          <Bar
            yAxisId="left"
            dataKey="discoveries"
            fill="#3b82f6"
            name="Videos Discovered"
            radius={[4, 4, 0, 0]}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="infringements"
            stroke="#ef4444"
            strokeWidth={2}
            name="Infringements"
            dot={{ fill: '#ef4444', r: 3 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
