import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

export type UserRole = 'admin' | 'editor' | 'legal' | 'read' | 'client'

export type User = {
  email: string
  name: string | null
  role: UserRole
  picture: string | null
}

type AuthContextType = {
  user: User | null
  actualUser: User | null  // The real logged-in user (for "Act As")
  loading: boolean
  error: string | null
  logout: () => void
  actAs: (email: string | null) => Promise<void>
  isActingAs: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [actualUser, setActualUser] = useState<User | null>(null)  // The real user
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actAsEmail, setActAsEmail] = useState<string | null>(() => {
    // Restore "Act As" from localStorage
    return localStorage.getItem('actAsEmail')
  })

  // Fetch current user from API on mount or when actAsEmail changes
  useEffect(() => {
    fetchCurrentUser()
  }, [actAsEmail])

  const fetchCurrentUser = async () => {
    try {
      setLoading(true)
      setError(null)

      const headers: HeadersInit = {
        credentials: 'include',
      }

      // For local development, send X-Dev-User header
      if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        headers['X-Dev-User'] = 'dev@copycat.local'
      }

      // Add X-Act-As header for admin impersonation
      if (actAsEmail) {
        headers['X-Act-As'] = actAsEmail
      }

      const response = await fetch('/api/users/me', {
        credentials: 'include',
        headers,
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch user: ${response.statusText}`)
      }

      const userData = await response.json()

      if (actAsEmail) {
        // If acting as someone, keep track of real user
        if (!actualUser) {
          // First time acting as - fetch actual user
          const actualHeaders: HeadersInit = {
            credentials: 'include',
          }

          // For local development, send X-Dev-User header
          if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            actualHeaders['X-Dev-User'] = 'dev@copycat.local'
          }

          const actualResponse = await fetch('/api/users/me', {
            credentials: 'include',
            headers: actualHeaders,
          })
          if (actualResponse.ok) {
            const actualUserData = await actualResponse.json()
            setActualUser(actualUserData)
          }
        }
        setUser(userData)
      } else {
        // Normal mode - user is the actual user
        setUser(userData)
        setActualUser(userData)
      }
    } catch (err) {
      console.error('Failed to fetch current user:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch user')
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const actAs = async (email: string | null) => {
    if (email) {
      localStorage.setItem('actAsEmail', email)
      setActAsEmail(email)
    } else {
      localStorage.removeItem('actAsEmail')
      setActAsEmail(null)
      // Reset to actual user
      setUser(actualUser)
    }
  }

  const logout = () => {
    // Clear act-as state
    localStorage.removeItem('actAsEmail')
    // For IAP, logout redirects to Google's logout URL
    window.location.href = '/_gcp_iap/clear_login_cookie'
  }

  const isActingAs = actAsEmail !== null

  return (
    <AuthContext.Provider value={{ user, actualUser, loading, error, logout, actAs, isActingAs }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
