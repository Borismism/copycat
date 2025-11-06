import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

interface ScanProgressNotificationProps {
  show: boolean
  onClose: () => void
  duration?: number
}

export default function ScanProgressNotification({
  show,
  onClose,
  duration = 10000
}: ScanProgressNotificationProps) {
  const navigate = useNavigate()

  useEffect(() => {
    if (show) {
      const timer = setTimeout(() => {
        onClose()
      }, duration)

      return () => clearTimeout(timer)
    }
  }, [show, onClose, duration])

  if (!show) return null

  const handleClick = () => {
    navigate('/dashboards/vision')
    onClose()
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 animate-slide-in">
      <div
        onClick={handleClick}
        className="bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg shadow-2xl p-4 pr-12 cursor-pointer hover:from-blue-700 hover:to-purple-700 transition-all transform hover:scale-105 relative"
        style={{ minWidth: '320px' }}
      >
        <button
          onClick={(e) => {
            e.stopPropagation()
            onClose()
          }}
          className="absolute top-2 right-2 text-white hover:text-gray-200 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="flex items-center gap-3">
          <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <div>
            <div className="font-bold text-lg">Scan Started!</div>
            <div className="text-sm text-blue-100">Click here to track progress →</div>
          </div>
        </div>
      </div>
    </div>
  )
}
