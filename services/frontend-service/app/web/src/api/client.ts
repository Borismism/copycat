const API_BASE = '/api'

export class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'APIError'
  }
}

// Global error handler for 403 errors
let globalErrorHandler: ((error: APIError) => void) | null = null

export function setGlobalErrorHandler(handler: (error: APIError) => void) {
  globalErrorHandler = handler
}

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  // Add X-Act-As header if acting as another user
  const actAsEmail = localStorage.getItem('actAsEmail')
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options?.headers,
  }

  if (actAsEmail) {
    headers['X-Act-As'] = actAsEmail
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    const apiError = new APIError(response.status, error.detail || error.message || 'Request failed')

    // Call global error handler for 403 errors
    if (response.status === 403 && globalErrorHandler) {
      globalErrorHandler(apiError)
    }

    throw apiError
  }

  return response.json()
}

export const api = {
  get: <T>(endpoint: string) => fetchAPI<T>(endpoint),
  post: <T>(endpoint: string, data?: unknown) =>
    fetchAPI<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),
  put: <T>(endpoint: string, data?: unknown) =>
    fetchAPI<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    }),
  delete: <T>(endpoint: string) =>
    fetchAPI<T>(endpoint, { method: 'DELETE' }),
}
