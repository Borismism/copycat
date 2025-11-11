/**
 * Global fetch wrapper that adds X-Act-As header to all API requests
 * and handles 403 errors globally
 */

import { APIError, setGlobalErrorHandler } from '../api/client'

const originalFetch = window.fetch

// Override global fetch
window.fetch = function (input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  // Only intercept /api/* requests
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url

  if (url.startsWith('/api/')) {
    const actAsEmail = localStorage.getItem('actAsEmail')

    if (actAsEmail) {
      // Add X-Act-As header
      init = init || {}
      init.headers = init.headers || {}

      if (init.headers instanceof Headers) {
        init.headers.set('X-Act-As', actAsEmail)
      } else if (Array.isArray(init.headers)) {
        init.headers.push(['X-Act-As', actAsEmail])
      } else {
        ;(init.headers as Record<string, string>)['X-Act-As'] = actAsEmail
      }
    }
  }

  // Call original fetch
  return originalFetch(input, init).then(async (response) => {
    // Handle 403 errors globally
    if (response.status === 403 && url.startsWith('/api/')) {
      const errorData = await response.clone().json().catch(() => ({ detail: 'Access denied' }))
      const error = new APIError(403, errorData.detail || 'Access denied')

      // Trigger global error handler
      // We need to get it from somewhere - let's use a global variable
      if ((window as any).__globalErrorHandler) {
        ;(window as any).__globalErrorHandler(error)
      }
    }

    return response
  })
}

// Store error handler globally so fetch wrapper can access it
export function initFetchWrapper(errorHandler: (error: APIError) => void) {
  ;(window as any).__globalErrorHandler = errorHandler
  setGlobalErrorHandler(errorHandler)
}
