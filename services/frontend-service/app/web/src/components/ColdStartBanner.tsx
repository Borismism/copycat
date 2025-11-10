import { useEffect, useState } from 'react'

interface ColdStartBannerProps {
  show: boolean
}

export default function ColdStartBanner({ show }: ColdStartBannerProps) {
  const [dots, setDots] = useState('.')
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!show) return

    // Animate dots
    const dotsInterval = setInterval(() => {
      setDots(prev => (prev.length >= 3 ? '.' : prev + '.'))
    }, 500)

    // Track elapsed time
    const startTime = Date.now()
    const timeInterval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)

    return () => {
      clearInterval(dotsInterval)
      clearInterval(timeInterval)
      setDots('.')
      setElapsed(0)
    }
  }, [show])

  if (!show) return null

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-8 shadow-lg">
      <div className="flex flex-col items-center space-y-6">
        {/* Animated spinner */}
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-200"></div>
          <div className="absolute top-0 left-0 animate-spin rounded-full h-16 w-16 border-t-4 border-blue-600"></div>
        </div>

        {/* Status message */}
        <div className="text-center space-y-2">
          <h3 className="text-xl font-semibold text-gray-900">
            Services are waking up{dots}
          </h3>
          <p className="text-gray-600">
            Cloud Run services are starting from cold state.
            <br />
            This typically takes 30-60 seconds on first load.
          </p>
          {elapsed > 10 && (
            <p className="text-sm text-gray-500 mt-2">
              Elapsed time: {elapsed}s
            </p>
          )}
        </div>

        {/* Progress indicator */}
        <div className="w-full max-w-md">
          <div className="bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-blue-600 h-full transition-all duration-1000 ease-out"
              style={{
                width: `${Math.min(elapsed * 1.67, 100)}%`, // 60s = 100%
              }}
            />
          </div>
        </div>

        {/* Tips */}
        <div className="text-xs text-gray-500 bg-white/50 rounded px-4 py-2 max-w-lg text-center">
          💡 Tip: Services will stay warm for a few minutes after the first request.
          Subsequent page loads will be instant.
        </div>
      </div>
    </div>
  )
}
