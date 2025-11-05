import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const navLinks = [
    { path: '/config', label: 'IP Configuration' },
    { path: '/', label: 'Dashboard' },
    { path: '/discovery', label: 'Discovery' },
    { path: '/risk', label: 'Risk Analyzer' },
    { path: '/vision', label: 'Vision Analyzer' },
    { path: '/videos', label: 'Videos' },
    { path: '/channels', label: 'Channels' },
  ]

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-bold text-gray-900">Copycat Management</h1>
            <div className="text-sm text-gray-500">AI Content Detection System</div>
          </div>

          {/* Navigation */}
          <nav className="flex space-x-4 border-t pt-4">
            {navLinks.map((link) => {
              const isActive = location.pathname === link.path
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
    </div>
  )
}
