import { createContext, useContext, useState, ReactNode } from 'react'

export type User = {
  id: string
  name: string
  email: string
  role: 'admin' | 'legal' | 'viewer'
}

type AuthContextType = {
  user: User | null
  login: (email: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Mock users for development
const MOCK_USERS: Record<string, User> = {
  'admin@copycat.com': {
    id: '1',
    name: 'Admin User',
    email: 'admin@copycat.com',
    role: 'admin',
  },
  'legal@copycat.com': {
    id: '2',
    name: 'Legal Team',
    email: 'legal@copycat.com',
    role: 'legal',
  },
  'viewer@copycat.com': {
    id: '3',
    name: 'Viewer',
    email: 'viewer@copycat.com',
    role: 'viewer',
  },
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    // Check localStorage for existing session
    const stored = localStorage.getItem('mockUser')
    return stored ? JSON.parse(stored) : null
  })

  const login = (email: string) => {
    const mockUser = MOCK_USERS[email.toLowerCase()]
    if (mockUser) {
      setUser(mockUser)
      localStorage.setItem('mockUser', JSON.stringify(mockUser))
    }
  }

  const logout = () => {
    setUser(null)
    localStorage.removeItem('mockUser')
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
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
