import { useEffect, useState } from 'react'
import { APIError } from '../api/client'
import { initFetchWrapper } from '../utils/fetch-wrapper'

export function GlobalErrorHandler({ children }: { children: React.ReactNode }) {
  const [error, setError] = useState<APIError | null>(null)

  useEffect(() => {
    // Set up global 403 error handler for BOTH api client AND direct fetch calls
    const errorHandler = (err: APIError) => {
      if (err.status === 403) {
        setError(err)
      }
    }

    initFetchWrapper(errorHandler)
  }, [])

  if (error) {
    const handleStopActingAs = () => {
      // Clear Act As state
      localStorage.removeItem('actAsEmail')
      window.location.reload()
    }

    const isActingAs = localStorage.getItem('actAsEmail') !== null

    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full mb-4">
            <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-2">Access Denied</h2>
          <p className="text-gray-600 text-center mb-6">{error.message}</p>

          <div className="space-y-3">
            {isActingAs && (
              <>
                <button
                  onClick={handleStopActingAs}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  Stop Acting As User
                </button>
                <button
                  onClick={() => window.location.reload()}
                  className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  Retry
                </button>
              </>
            )}
            {!isActingAs && (
              <button
                onClick={() => window.location.reload()}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
