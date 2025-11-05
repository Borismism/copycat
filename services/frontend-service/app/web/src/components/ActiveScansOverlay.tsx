import { useEffect, useState } from 'react'
import { videosAPI } from '../api/videos'
import type { VideoMetadata } from '../types'

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

interface ScanItemProgress {
  videoId: string
  progress: ScanProgress
  progressPercent: number
  processingStartTime: number | null
}

// Export the type so parent can use it
export interface ScanItemProgress {
  videoId: string
  progress: ScanProgress
  progressPercent: number
  processingStartTime: number | null
}

interface ScanProgress {
  status: 'queued' | 'published' | 'processing' | 'completed' | 'failed' | 'timeout' | 'error'
  message: string
  elapsed?: number
  processing_started_at?: number
  infringement?: boolean
  confidence?: number
  characters?: string[]
  error_type?: string
  error_message?: string
}

interface ActiveScansOverlayProps {
  onViewProgress: (videoId: string) => void
  onScansChanged?: (count: number) => void
  scanProgress: Map<string, ScanItemProgress>  // Receive from parent
  setScanProgress: React.Dispatch<React.SetStateAction<Map<string, ScanItemProgress>>>  // Receive from parent
}

// ScanItem Component - handles individual scan progress with its own hooks
interface ScanItemProps {
  video: VideoMetadata
  scanProgress: Map<string, ScanItemProgress>
  setScanProgress: React.Dispatch<React.SetStateAction<Map<string, ScanItemProgress>>>
  setErrorVideos: React.Dispatch<React.SetStateAction<Map<string, { video: VideoMetadata, error: string, timestamp: number }>>>
  onViewProgress: (videoId: string) => void
}

function ScanItem({ video, scanProgress, setScanProgress, setErrorVideos, onViewProgress }: ScanItemProps) {
  // Initialize state if not exists - ONLY RUN ONCE per video_id
  useEffect(() => {
    setScanProgress(prev => {
      if (prev.has(video.video_id)) return prev // Already initialized - DON'T re-run

      // Calculate start time and initial progress
      const actualStartTime = video.processing_started_at
        ? Math.floor(new Date(video.processing_started_at).getTime() / 1000)
        : null

      let initialProgress = 0
      if (actualStartTime) {
        const elapsed = (Date.now() / 1000) - actualStartTime
        initialProgress = Math.min(98, 98 * (1 - Math.exp(-elapsed / 12)))
      }

      const next = new Map(prev)
      next.set(video.video_id, {
        videoId: video.video_id,
        progress: { status: 'processing', message: 'Analyzing...' },
        progressPercent: initialProgress,
        processingStartTime: actualStartTime
      })
      return next
    })
  }, [video.video_id]) // ONLY depend on video_id, not on actualStartTime

  // Continuously update progress based on actual start time
  useEffect(() => {
    const updateProgress = () => {
      setScanProgress(prev => {
        const current = prev.get(video.video_id)
        if (!current) return prev

        // Don't update if completed/failed
        if (current.progress.status === 'completed' || current.progress.status === 'failed' || current.progress.status === 'error') {
          return prev
        }

        // Get start time from stored state
        const startTime = current.processingStartTime
        if (!startTime) return prev

        const elapsed = (Date.now() / 1000) - startTime
        const progressPercent = Math.min(98, 98 * (1 - Math.exp(-elapsed / 12)))

        const next = new Map(prev)
        next.set(video.video_id, {
          ...current,
          progressPercent
        })
        return next
      })
    }

    // Update immediately
    updateProgress()

    // Update every second
    const interval = setInterval(updateProgress, 1000)
    return () => clearInterval(interval)
  }, [video.video_id]) // ONLY depend on video_id

  // Subscribe to SSE updates for status changes only
  useEffect(() => {
    let isCompleted = false
    const eventSource = new EventSource(`http://localhost:8080/api/videos/${video.video_id}/scan/stream`)

    eventSource.onmessage = (event) => {
      try {
        const data: ScanProgress = JSON.parse(event.data)

        setScanProgress(prev => {
          const next = new Map(prev)
          const current = next.get(video.video_id)

          if (!current) {
            // Shouldn't happen since we initialize in first useEffect, but handle gracefully
            return prev
          }

          // IMPORTANT: Keep existing progressPercent from timer
          // Only override if status is completed (snap to 100%)
          let progressPercent = current.progressPercent
          if (data.status === 'completed') {
            progressPercent = 100
          }
          // For all other statuses, let the timer handle progress updates

          next.set(video.video_id, {
            videoId: video.video_id,
            progress: data,  // Update status and message from SSE
            progressPercent,  // Keep progress from timer (or 100% if completed)
            processingStartTime: current.processingStartTime  // Keep existing start time
          })
          return next
        })

        if (data.status === 'completed') {
          isCompleted = true
          eventSource.close()
        }

        if (data.status === 'failed' || data.status === 'error' || data.status === 'timeout') {
          isCompleted = true
          eventSource.close()
          // Add to error list
          setErrorVideos(prev => new Map(prev).set(video.video_id, {
            video,
            error: data.error_message || data.error_type || 'Unknown error',
            timestamp: Date.now()
          }))
        }
      } catch (err) {
        console.error('Failed to parse SSE data:', err)
      }
    }

    eventSource.onerror = () => {
      if (!isCompleted) {
        setScanProgress(prev => {
          const next = new Map(prev)
          next.set(video.video_id, {
            ...videoProgress,
            progress: { status: 'error', message: 'Connection lost' }
          })
          return next
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
  }, [video.video_id])

  // Get current progress from state
  const videoProgress = scanProgress.get(video.video_id)

  // Don't render if not initialized yet
  if (!videoProgress) return null

  const getStatusColor = () => {
    switch (videoProgress.progress.status) {
      case 'completed': return 'border-green-500 bg-green-50'
      case 'failed':
      case 'error': return 'border-red-500 bg-red-50'
      case 'timeout': return 'border-yellow-500 bg-yellow-50'
      default: return 'border-orange-300 bg-white'
    }
  }

  return (
    <div className={`p-3 border-b border-gray-200 ${getStatusColor()} transition-colors`}>
      <div className="flex items-start gap-3">
        {/* Thumbnail */}
        <div className="flex-shrink-0 w-16 h-12 bg-gray-200 rounded overflow-hidden">
          <img
            src={video.thumbnail_url || `https://i.ytimg.com/vi/${video.video_id}/default.jpg`}
            alt=""
            className="w-full h-full object-cover"
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <a
            href={`https://youtube.com/watch?v=${video.video_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-blue-600 hover:text-blue-800 hover:underline line-clamp-2 leading-tight mb-1 block"
          >
            {video.title}
          </a>
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    videoProgress.progress.status === 'failed' || videoProgress.progress.status === 'error' ? 'bg-red-600' :
                    videoProgress.progress.status === 'completed' ? 'bg-green-600' :
                    'bg-orange-600'
                  }`}
                  style={{ width: `${videoProgress.progressPercent}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {Math.round(videoProgress.progressPercent)}% - {videoProgress.progress.message}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* View Progress Button */}
      <button
        onClick={() => onViewProgress(video.video_id)}
        className="mt-2 w-full flex items-center justify-center gap-1 px-2 py-1.5 bg-orange-600 text-white text-xs font-medium rounded hover:bg-orange-700 transition-colors"
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
        </svg>
        View Details
      </button>
    </div>
  )
}

export default function ActiveScansOverlay({ onViewProgress, onScansChanged, scanProgress, setScanProgress }: ActiveScansOverlayProps) {
  const [processingVideos, setProcessingVideos] = useState<VideoMetadata[]>([])
  const [errorVideos, setErrorVideos] = useState<Map<string, { video: VideoMetadata, error: string, timestamp: number }>>(new Map())
  const [isOpen, setIsOpen] = useState(true)
  const [isMinimized, setIsMinimized] = useState(false)
  const [previousCount, setPreviousCount] = useState(0)

  // Poll for processing videos every 5 seconds
  useEffect(() => {
    const loadProcessingVideos = async () => {
      try {
        const data = await videosAPI.listProcessing()
        const videos = data.processing_videos || []
        const newCount = videos.length

        setProcessingVideos(videos)

        // Notify parent when count changes (especially when scans complete)
        if (newCount !== previousCount) {
          onScansChanged?.(newCount)
          setPreviousCount(newCount)
        }

        // Auto-close and reset when all scans complete and no errors
        if (videos.length === 0 && errorVideos.size === 0) {
          setIsOpen(false)
          setIsMinimized(false)
        } else if (videos.length > 0 && !isOpen && !isMinimized) {
          // Auto-open when new scans start
          setIsOpen(true)
        }
      } catch (err) {
        console.error('Failed to load processing videos:', err)
      }
    }

    loadProcessingVideos()
    const interval = setInterval(loadProcessingVideos, 5000)
    return () => clearInterval(interval)
  }, [previousCount, onScansChanged, errorVideos.size, isOpen, isMinimized])

  // Don't render if no processing videos and no errors
  if (processingVideos.length === 0 && errorVideos.size === 0) return null

  // Minimized badge
  if (isMinimized) {
    const totalCount = processingVideos.length + errorVideos.size
    return (
      <div className="fixed bottom-6 right-6 z-40">
        <button
          onClick={() => {
            setIsMinimized(false)
            setIsOpen(true)
          }}
          className="relative group"
          title={`${totalCount} active scan${totalCount > 1 ? 's' : ''}${errorVideos.size > 0 ? ` (${errorVideos.size} error${errorVideos.size > 1 ? 's' : ''})` : ''}`}
        >
          <svg className={`w-8 h-8 ${errorVideos.size > 0 ? 'text-red-600 hover:text-red-700' : 'text-orange-600 hover:text-orange-700'} transition-all hover:scale-110 drop-shadow-lg`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
          </svg>
          {totalCount > 0 && (
            <span className={`absolute -top-1 -right-1 ${errorVideos.size > 0 ? 'bg-red-500' : 'bg-orange-500'} text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center shadow-lg animate-pulse`}>
              {totalCount}
            </span>
          )}
        </button>
      </div>
    )
  }

  // Full overlay
  return (
    <div className="fixed bottom-6 right-6 z-40 w-96">
      <div className="bg-white rounded-lg shadow-2xl border-2 border-orange-300 overflow-hidden">
        {/* Header */}
        <div className={`${errorVideos.size > 0 ? 'bg-red-600' : 'bg-orange-600'} text-white px-4 py-3 flex items-center justify-between`}>
          <div className="flex items-center gap-2">
            {errorVideos.size === 0 ? (
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            <span className="font-bold text-sm">
              {processingVideos.length} Active Scan{processingVideos.length !== 1 ? 's' : ''}
              {errorVideos.size > 0 && ` • ${errorVideos.size} Error${errorVideos.size !== 1 ? 's' : ''}`}
            </span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                setIsMinimized(true)
                setIsOpen(false)
              }}
              className={`${errorVideos.size > 0 ? 'hover:bg-red-700' : 'hover:bg-orange-700'} p-1 rounded transition-colors`}
              title="Minimize"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className={`${errorVideos.size > 0 ? 'hover:bg-red-700' : 'hover:bg-orange-700'} p-1 rounded transition-colors`}
              title="Close"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        {isOpen && (
          <div className="max-h-[32rem] overflow-y-auto">
            {processingVideos.map(video => (
              <ScanItem
                key={video.video_id}
                video={video}
                scanProgress={scanProgress}
                setScanProgress={setScanProgress}
                setErrorVideos={setErrorVideos}
                onViewProgress={onViewProgress}
              />
            ))}

            {/* Error Messages Section */}
            {errorVideos.size > 0 && (
              <div className="bg-red-50 border-t-2 border-red-300">
                <div className="px-4 py-2 bg-red-100 border-b border-red-200">
                  <h4 className="text-red-800 font-semibold text-xs flex items-center gap-1">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Recent Errors
                  </h4>
                </div>
                {Array.from(errorVideos.values()).map(({ video, error, timestamp }) => (
                  <div
                    key={video.video_id}
                    className="p-3 border-b border-red-200 last:border-b-0"
                  >
                    <div className="flex items-start justify-between mb-1">
                      <p className="text-red-900 font-medium text-xs truncate flex-1">
                        {video.title}
                      </p>
                      <button
                        onClick={() => {
                          setErrorVideos(prev => {
                            const next = new Map(prev)
                            next.delete(video.video_id)
                            return next
                          })
                        }}
                        className="text-red-600 hover:text-red-800 ml-2"
                        title="Dismiss"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <p className="text-red-700 font-mono text-xs bg-red-100 p-1 rounded">{error}</p>
                    <p className="text-red-600 text-xs mt-1">
                      {new Date(timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Collapsed state */}
        {!isOpen && (
          <button
            onClick={() => setIsOpen(true)}
            className="w-full p-3 text-sm text-gray-600 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
          >
            <span>Show details</span>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
