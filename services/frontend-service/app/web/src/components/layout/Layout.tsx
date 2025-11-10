import { ReactNode, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { user, actualUser, loading, logout, actAs, isActingAs } = useAuth()
  const [showActAsModal, setShowActAsModal] = useState(false)
  const [actAsEmail, setActAsEmail] = useState('')

  const navLinks = [
    { path: '/', label: 'Home' },
    { path: '/dashboards', label: 'Services' },
    { path: '/config', label: 'IP Configuration' },
    { path: '/videos', label: 'Videos' },
    { path: '/channels', label: 'Enforcement' },
  ]

  // Add admin-only routes (check actualUser for real admin, not impersonated)
  if (actualUser?.role === 'admin') {
    navLinks.push({ path: '/admin/roles', label: 'User Roles' })
  }

  const handleActAs = async (e: React.FormEvent) => {
    e.preventDefault()
    if (actAsEmail.trim()) {
      await actAs(actAsEmail.trim())
      setShowActAsModal(false)
      setActAsEmail('')
    }
  }

  const handleStopActingAs = async () => {
    await actAs(null)
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
              {loading ? (
                <div className="text-sm text-gray-500">Loading...</div>
              ) : user ? (
                <>
                  {/* Act As Banner */}
                  {isActingAs && (
                    <div className="flex items-center gap-2 px-3 py-1 bg-yellow-100 border border-yellow-300 rounded-lg">
                      <span className="text-sm font-medium text-yellow-900">
                        Acting as: {user.email}
                      </span>
                      <button
                        onClick={handleStopActingAs}
                        className="text-xs px-2 py-0.5 bg-yellow-200 hover:bg-yellow-300 text-yellow-900 rounded transition-colors"
                      >
                        Stop
                      </button>
                    </div>
                  )}

                  <div className="flex items-center gap-3">
                    {user.picture && (
                      <img
                        src={user.picture}
                        alt={user.name || user.email}
                        className="w-8 h-8 rounded-full"
                      />
                    )}
                    <div className="text-sm">
                      <div className="font-medium text-gray-900">{user.name || user.email}</div>
                      <div className="text-gray-500 capitalize">{user.role}</div>
                    </div>
                  </div>

                  {/* Admin "Act As" button */}
                  {actualUser?.role === 'admin' && !isActingAs && (
                    <button
                      onClick={() => setShowActAsModal(true)}
                      className="px-3 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                    >
                      Act As
                    </button>
                  )}

                  <button
                    onClick={logout}
                    className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <div className="text-sm text-red-600">Not authenticated</div>
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

      {/* Act As Modal */}
      {showActAsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
            <h3 className="text-xl font-bold text-gray-900 mb-4">Act As User</h3>
            <p className="text-sm text-gray-600 mb-4">
              Enter the email address of the user you want to impersonate. This is an admin-only feature for testing role-based permissions.
            </p>

            <form onSubmit={handleActAs} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  User Email
                </label>
                <input
                  type="email"
                  value={actAsEmail}
                  onChange={(e) => setActAsEmail(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  placeholder="user@example.com"
                  autoFocus
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowActAsModal(false)
                    setActAsEmail('')
                  }}
                  className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                >
                  Act As
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
