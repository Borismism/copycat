import { useEffect, useState } from 'react'
import { videosAPI } from '../api/videos'
import type { VideoMetadata } from '../types'

interface ScanItemProgress {
  videoId: string
  progress: ScanProgress
  progressPercent: number
  processingStartTime: number | null
}

interface ScanProgressModalProps {
  videoId: string
  scanProgress: Map<string, ScanItemProgress>  // SINGLE SOURCE OF TRUTH
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

export default function ScanProgressModal({
  videoId,
  scanProgress,
  onClose,
}: ScanProgressModalProps) {
  const [video, setVideo] = useState<VideoMetadata | null>(null)

  // Fetch video metadata for display
  useEffect(() => {
    videosAPI.getVideo(videoId).then(setVideo).catch(console.error)
  }, [videoId])

  // Get progress from SINGLE SOURCE OF TRUTH (shared state with overlay)
  // Overlay creates new Map on each update, which triggers re-render here
  const videoProgress = scanProgress.get(videoId)

  if (!videoProgress) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-8 text-center">
          <p className="text-gray-600">Loading scan progress...</p>
        </div>
      </div>
    )
  }

  const { progress, progressPercent } = videoProgress

  const getStatusIcon = () => {
    switch (progress.status) {
      case 'queued':
      case 'published':
      case 'processing':
        return (
          <svg className="animate-spin h-12 w-12 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )
      case 'completed':
        return (
          <svg className="h-12 w-12 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
        )
      case 'failed':
      case 'error':
        return (
          <svg className="h-12 w-12 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        )
      case 'timeout':
        return (
          <svg className="h-12 w-12 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        )
      default:
        return null
    }
  }

  const getStatusColor = () => {
    switch (progress.status) {
      case 'completed':
        return 'text-green-600'
      case 'failed':
      case 'error':
        return 'text-red-600'
      case 'timeout':
        return 'text-yellow-600'
      default:
        return 'text-blue-600'
    }
  }

  // Show loading state while fetching video
  if (!video) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-8 text-center">
          <p className="text-gray-600">Loading video details...</p>
        </div>
      </div>
    )
  }

  // Full modal view
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4 flex justify-between items-start">
          <div className="flex-1">
            <h2 className="text-xl font-bold text-white mb-1">Video Analysis Progress</h2>
            <p className="text-blue-100 text-sm">Real-time Gemini AI scanning</p>
          </div>
          {/* Close button */}
          <button
            onClick={onClose}
            className="text-blue-100 hover:text-white transition-colors ml-4"
            title="Close"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6">
          {/* Video Info Card */}
          <div className="mb-6 p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg border-2 border-blue-200">
            <div className="flex gap-4">
              {/* Thumbnail */}
              <div className="flex-shrink-0">
                <img
                  src={video.thumbnail_url || `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`}
                  alt="Video thumbnail"
                  className="w-32 h-24 object-cover rounded border border-gray-300"
                />
              </div>
              {/* Video Details */}
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 uppercase font-semibold mb-1">Analyzing Video</p>
                <a
                  href={`https://youtube.com/watch?v=${videoId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-base text-blue-600 hover:text-blue-800 hover:underline font-medium leading-tight block mb-2"
                >
                  {video.title}
                </a>
                <p className="text-xs text-gray-500 font-mono bg-white px-2 py-1 rounded border border-gray-200 inline-block">
                  ID: {videoId}
                </p>
              </div>
            </div>
          </div>

          {/* Status Icon and Message */}
          <div className="flex flex-col items-center mb-6">
            <div className="mb-4">{getStatusIcon()}</div>
            <div className="text-center">
              <p className={`text-lg font-semibold ${getStatusColor()} mb-2`}>{progress.message}</p>
              {progress.elapsed && (
                <p className="text-sm text-gray-500">
                  Time elapsed: <span className="font-medium">{progress.elapsed}s</span>
                </p>
              )}
            </div>
          </div>

          {/* Error Details */}
          {(progress.status === 'failed' || progress.status === 'error') && (
            <div className="p-4 rounded-lg border-2 bg-red-50 border-red-300">
              <div className="flex items-start gap-3 mb-2">
                <svg className="w-6 h-6 text-red-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-bold text-red-900 mb-1">
                    {progress.error_type || 'Error'}
                  </p>
                  <p className="text-xs text-red-800 font-mono bg-red-100 p-2 rounded">
                    {progress.error_message || 'An unknown error occurred'}
                  </p>
                </div>
              </div>
              <div className="text-xs text-red-700 mt-2">
                The video status has been marked as failed. You can try scanning again later.
              </div>
            </div>
          )}

          {/* Results (on completion) */}
          {progress.status === 'completed' && (
            <div className="p-4 rounded-lg border-2" style={{
              backgroundColor: progress.infringement ? '#fee2e2' : '#d1fae5',
              borderColor: progress.infringement ? '#ef4444' : '#10b981'
            }}>
              <div className="flex items-center justify-between mb-2">
                <span className={`text-sm font-bold ${progress.infringement ? 'text-red-900' : 'text-green-900'}`}>
                  {progress.infringement ? '⚠️ INFRINGEMENT DETECTED' : '✅ NO INFRINGEMENT'}
                </span>
                <span className={`text-sm font-medium ${progress.infringement ? 'text-red-700' : 'text-green-700'}`}>
                  {progress.confidence}% confidence
                </span>
              </div>
              {progress.characters && progress.characters.length > 0 && (
                <div className="text-xs text-gray-700">
                  Characters: {progress.characters.join(', ')}
                </div>
              )}
            </div>
          )}

          {/* Smart Progress Bar */}
          {(progress.status === 'queued' || progress.status === 'published' || progress.status === 'processing') && (
            <div>
              <div className="flex justify-between items-center text-sm text-gray-600 mb-2">
                <span className="font-medium">Analysis Progress</span>
                <span className="font-bold text-blue-600">{Math.round(progressPercent)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden shadow-inner">
                <div
                  className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-500 ease-out shadow-sm"
                  style={{
                    width: `${progressPercent}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-center gap-2 mt-3 text-xs text-gray-500">
                <svg className="animate-pulse w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
                </svg>
                <span>
                  {progress.status === 'processing' ? 'Gemini AI is analyzing the video...' : 'Setting up scan...'}
                </span>
              </div>
            </div>
          )}

          {/* Close Button (on completion or error) */}
          {(progress.status === 'completed' || progress.status === 'failed' || progress.status === 'error' || progress.status === 'timeout') && (
            <button
              onClick={onClose}
              className="mt-6 w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 transition-colors font-semibold shadow-md hover:shadow-lg"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
