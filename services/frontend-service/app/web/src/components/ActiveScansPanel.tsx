import { useState } from 'react'

export interface ActiveScan {
  id: string
  type: 'video' | 'channel-scan' | 'channel-discover'
  title: string
  subtitle?: string
  status: 'running' | 'completed' | 'failed'
  progress?: number
  message?: string
  result?: {
    queued?: number
    analyzed?: number
    skipped?: number
    found?: number
    new?: number
  }
}

interface ActiveScansPanelProps {
  scans: ActiveScan[]
  onOpenScan: (scanId: string) => void
  onClearCompleted: () => void
}

export default function ActiveScansPanel({
  scans,
  onOpenScan,
  onClearCompleted,
}: ActiveScansPanelProps) {
  const [isOpen, setIsOpen] = useState(false)

  const runningScans = scans.filter(s => s.status === 'running')
  const completedScans = scans.filter(s => s.status === 'completed')
  const failedScans = scans.filter(s => s.status === 'failed')
  const totalScans = scans.length

  if (totalScans === 0) {
    return null // Don't show if no scans
  }

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-6 right-6 z-40 px-4 py-3 rounded-full shadow-2xl font-medium text-white transition-all transform hover:scale-105 ${
          runningScans.length > 0
            ? 'bg-blue-600 hover:bg-blue-700 animate-pulse'
            : completedScans.length > 0
            ? 'bg-green-600 hover:bg-green-700'
            : 'bg-red-600 hover:bg-red-700'
        }`}
      >
        <div className="flex items-center gap-2">
          {runningScans.length > 0 ? (
            <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          ) : completedScans.length > 0 ? (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
          <span>
            {runningScans.length > 0 && `${runningScans.length} Active`}
            {runningScans.length === 0 && completedScans.length > 0 && `${completedScans.length} Complete`}
            {runningScans.length === 0 && completedScans.length === 0 && `${failedScans.length} Failed`}
          </span>
        </div>
      </button>

      {/* Slide-out Panel */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/30 z-40 transition-opacity"
            onClick={() => setIsOpen(false)}
          />

          {/* Panel */}
          <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-2xl z-50 transform transition-transform overflow-hidden flex flex-col">
            {/* Header */}
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4 flex justify-between items-center flex-shrink-0">
              <div>
                <h2 className="text-xl font-bold text-white">Active Scans</h2>
                <p className="text-blue-100 text-sm">
                  {runningScans.length} running • {completedScans.length} completed
                </p>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-blue-100 hover:text-white transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Actions */}
            {completedScans.length > 0 && (
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-200 flex-shrink-0">
                <button
                  onClick={onClearCompleted}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  Clear {completedScans.length} completed
                </button>
              </div>
            )}

            {/* Scans List */}
            <div className="flex-1 overflow-y-auto">
              {scans.map((scan) => (
                <div
                  key={scan.id}
                  className={`px-6 py-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors ${
                    scan.status === 'running' ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => onOpenScan(scan.id)}
                >
                  {/* Type Badge */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                      scan.type === 'video' ? 'bg-purple-100 text-purple-700' :
                      scan.type === 'channel-scan' ? 'bg-blue-100 text-blue-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {scan.type === 'video' ? '📹 Video' :
                       scan.type === 'channel-scan' ? '📊 Scan' :
                       '🔍 Discover'}
                    </span>
                    <span className={`text-xs font-medium ${
                      scan.status === 'running' ? 'text-blue-600' :
                      scan.status === 'completed' ? 'text-green-600' :
                      'text-red-600'
                    }`}>
                      {scan.status === 'running' && 'Running...'}
                      {scan.status === 'completed' && '✓ Complete'}
                      {scan.status === 'failed' && '✗ Failed'}
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="font-medium text-gray-900 text-sm mb-1 truncate">{scan.title}</h3>
                  {scan.subtitle && (
                    <p className="text-xs text-gray-500 mb-2 truncate">{scan.subtitle}</p>
                  )}

                  {/* Progress Bar (for running scans) */}
                  {scan.status === 'running' && scan.progress !== undefined && (
                    <div className="mb-2">
                      <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${scan.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Message */}
                  {scan.message && (
                    <p className="text-xs text-gray-600 mb-2">{scan.message}</p>
                  )}

                  {/* Results (for completed) */}
                  {scan.status === 'completed' && scan.result && (
                    <div className="flex gap-4 text-xs text-gray-600 mt-2">
                      {scan.result.queued !== undefined && (
                        <span>Queued: <strong>{scan.result.queued}</strong></span>
                      )}
                      {scan.result.analyzed !== undefined && (
                        <span>Analyzed: <strong>{scan.result.analyzed}</strong></span>
                      )}
                      {scan.result.found !== undefined && (
                        <span>Found: <strong>{scan.result.found}</strong></span>
                      )}
                      {scan.result.new !== undefined && (
                        <span>New: <strong>{scan.result.new}</strong></span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  )
}
