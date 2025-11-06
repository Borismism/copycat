import { useEffect, useState } from 'react'

interface CompactScanWidgetProps {
  videoId: string
  videoTitle: string
  onOpenDetail: () => void
  onComplete: (result: any) => void
  onClose: () => void
}

interface ScanProgress {
  status: 'queued' | 'published' | 'processing' | 'completed' | 'failed' | 'timeout' | 'error'
  message: string
  elapsed?: number
  processing_started_at?: number // Unix timestamp in seconds
  infringement?: boolean
  confidence?: number
  characters?: string[]
  error_type?: string
  error_message?: string
}

export default function CompactScanWidget({
  videoId,
  videoTitle,
  onOpenDetail,
  onComplete,
  onClose,
}: CompactScanWidgetProps) {
  const [progress, setProgress] = useState<ScanProgress>({
    status: 'queued',
    message: 'Initializing scan...',
  })
  const [progressPercent, setProgressPercent] = useState(0)
  const [processingStartTime, setProcessingStartTime] = useState<number | null>(null)

  // Asymptotic progress algorithm - reaches ~98% over 30 seconds
  // Uses server-provided elapsed time or processing_started_at for accurate synchronization
  useEffect(() => {
    if (progress.status === 'completed') {
      // Snap to 100% on completion
      setProgressPercent(100)

      // Auto-close after 3 seconds
      const timer = setTimeout(() => {
        onClose()
      }, 3000)

      return () => clearTimeout(timer)
    }

    if (progress.status === 'failed' || progress.status === 'error' || progress.status === 'timeout') {
      // Keep progress bar at current state for errors
      return
    }

    // Calculate asymptotic progress based on elapsed time
    const updateProgress = () => {
      let elapsed = 0

      // Priority 1: Use server-provided elapsed time (most accurate)
      if (progress.elapsed !== undefined) {
        elapsed = progress.elapsed
      }
      // Priority 2: Calculate from processing_started_at timestamp (synchronized across all components)
      else if (processingStartTime) {
        elapsed = (Date.now() / 1000) - processingStartTime
      }

      // Asymptotic formula: approaches 98% over 30 seconds
      // Formula: 98 * (1 - e^(-elapsed/12))
      // This gives: 5s→33%, 10s→55%, 20s→80%, 30s→92%, 40s→96%
      const asymptotic = 98 * (1 - Math.exp(-elapsed / 12))

      setProgressPercent(Math.min(98, asymptotic))
    }

    updateProgress()
    const interval = setInterval(updateProgress, 500) // Update every 0.5s for smooth animation

    return () => clearInterval(interval)
  }, [progress.status, progress.elapsed, processingStartTime, onClose])

  // Connect to SSE endpoint
  useEffect(() => {
    let isCompleted = false

    const eventSource = new EventSource(
      `/api/videos/${videoId}/scan/stream`
    )

    eventSource.onmessage = (event) => {
      try {
        const data: ScanProgress = JSON.parse(event.data)
        setProgress(data)

        // Capture processing start time if provided (for accurate synchronization)
        if (data.processing_started_at && !processingStartTime) {
          setProcessingStartTime(data.processing_started_at)
        }

        if (data.status === 'completed') {
          isCompleted = true
          eventSource.close()

          // Notify parent
          setTimeout(() => {
            onComplete(data)
          }, 3500) // Slightly longer than auto-close to let animation finish
          return
        }

        if (data.status === 'failed' || data.status === 'error' || data.status === 'timeout') {
          isCompleted = true
          eventSource.close()
          // Don't auto-close on errors - stay visible so user can see the error
        }
      } catch (err) {
        console.error('Failed to parse SSE data:', err)
      }
    }

    eventSource.onerror = () => {
      if (!isCompleted) {
        setProgress({
          status: 'error',
          message: 'Connection lost. Please try again.',
        })
      }
      try {
        eventSource.close()
      } catch (e) {
        // Already closed
      }
    }

    return () => {
      eventSource.close()
    }
  }, [videoId, onComplete])

  const getStatusColor = () => {
    switch (progress.status) {
      case 'completed':
        return 'bg-green-500'
      case 'failed':
      case 'error':
        return 'bg-red-500'
      case 'timeout':
        return 'bg-yellow-500'
      default:
        return 'bg-blue-500'
    }
  }

  const getStatusIcon = () => {
    switch (progress.status) {
      case 'completed':
        return (
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
        )
      case 'failed':
      case 'error':
        return (
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        )
      case 'timeout':
        return (
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )
      default:
        return (
          <svg className="animate-spin w-5 h-5 text-white" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )
    }
  }

  return (
    <div className="fixed bottom-6 right-6 z-40">
      <button
        onClick={onOpenDetail}
        className={`${getStatusColor()} rounded-lg shadow-xl hover:shadow-2xl transition-all transform hover:scale-105 p-4 min-w-[280px]`}
      >
        <div className="flex items-center gap-3">
          {/* Status Icon */}
          <div className="flex-shrink-0">
            {getStatusIcon()}
          </div>

          {/* Content */}
          <div className="flex-1 text-left">
            <p className="text-white font-semibold text-sm leading-tight mb-1">
              {progress.status === 'completed' ? 'Scan Complete!' :
               progress.status === 'failed' || progress.status === 'error' ? 'Scan Failed' :
               progress.status === 'timeout' ? 'Scan Timeout' :
               'Scanning Video...'}
            </p>
            <p className="text-white/80 text-xs truncate mb-2">
              {videoTitle.length > 30 ? videoTitle.substring(0, 30) + '...' : videoTitle}
            </p>

            {/* Error Message (for failed scans) */}
            {(progress.status === 'failed' || progress.status === 'error') && progress.error_message && (
              <p className="text-white/90 text-xs font-mono bg-white/20 p-1 rounded mb-2 truncate" title={progress.error_message}>
                {progress.error_message}
              </p>
            )}

            {/* Progress Bar (only show for active scans) */}
            {progress.status !== 'failed' && progress.status !== 'error' && progress.status !== 'timeout' && (
              <>
                <div className="w-full bg-white/30 rounded-full h-2 mb-1">
                  <div
                    className="bg-white h-2 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                {/* Progress Percentage */}
                <p className="text-white/90 text-xs font-medium">
                  {Math.round(progressPercent)}% complete
                </p>
              </>
            )}

            {/* Error/Timeout status text */}
            {(progress.status === 'failed' || progress.status === 'error' || progress.status === 'timeout') && (
              <p className="text-white/90 text-xs font-medium">
                {progress.error_type || progress.message}
              </p>
            )}
          </div>

          {/* Close button */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onClose()
            }}
            className="flex-shrink-0 text-white/60 hover:text-white transition-colors"
            title="Close"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </button>
    </div>
  )
}
