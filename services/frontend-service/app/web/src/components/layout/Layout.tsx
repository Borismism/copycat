import { ReactNode, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { user, login, logout } = useAuth()
  const [showLoginModal, setShowLoginModal] = useState(false)

  const navLinks = [
    { path: '/', label: 'Home' },
    { path: '/dashboards', label: 'Dashboards' },
    { path: '/config', label: 'IP Configuration' },
    { path: '/videos', label: 'Videos' },
    { path: '/channels', label: 'Enforcement' },
  ]

  const handleLogin = (email: string) => {
    login(email)
    setShowLoginModal(false)
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Copycat Management</h1>
              <div className="text-sm text-gray-500">AI Content Detection System</div>
            </div>
            <div className="flex items-center gap-4">
              {user ? (
                <>
                  <span className="text-sm text-gray-700">
                    <span className="font-medium">{user.name}</span>
                    <span className="text-gray-500 ml-2">({user.role})</span>
                  </span>
                  <button
                    onClick={logout}
                    className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setShowLoginModal(true)}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Login
                </button>
              )}
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex space-x-4 border-t pt-4">
            {navLinks.map((link) => {
              const isActive = location.pathname === link.path || location.pathname.startsWith(link.path + '/')
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  {link.label}
                </Link>
              )
            })}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-8 sm:px-6 lg:px-8" style={{ maxWidth: '1400px' }}>{children}</main>

      {/* Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
            <h3 className="text-xl font-bold text-gray-900 mb-4">Mock Login</h3>
            <p className="text-sm text-gray-600 mb-6">
              Select a mock user to login as:
            </p>
            <div className="space-y-3">
              <button
                onClick={() => handleLogin('admin@copycat.com')}
                className="w-full px-4 py-3 text-left bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
              >
                <div className="font-medium text-gray-900">Admin User</div>
                <div className="text-sm text-gray-600">admin@copycat.com (Full access)</div>
              </button>
              <button
                onClick={() => handleLogin('legal@copycat.com')}
                className="w-full px-4 py-3 text-left bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
              >
                <div className="font-medium text-gray-900">Legal Team</div>
                <div className="text-sm text-gray-600">legal@copycat.com (Enforcement access)</div>
              </button>
              <button
                onClick={() => handleLogin('viewer@copycat.com')}
                className="w-full px-4 py-3 text-left bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
              >
                <div className="font-medium text-gray-900">Viewer</div>
                <div className="text-sm text-gray-600">viewer@copycat.com (Read-only)</div>
              </button>
            </div>
            <button
              onClick={() => setShowLoginModal(false)}
              className="mt-4 w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
