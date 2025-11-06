import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import DiscoveryPage from './DiscoveryPage'
import VisionAnalyzerPage from './VisionAnalyzerPage'

export default function DashboardsPage() {
  const location = useLocation()
  const navigate = useNavigate()

  // Determine active tab from URL
  const getActiveTab = () => {
    if (location.pathname === '/dashboards/vision') return 'vision'
    return 'discovery'
  }

  const [activeTab, setActiveTab] = useState(getActiveTab())

  const tabs = [
    { id: 'discovery', label: 'Discovery', path: '/dashboards/discovery' },
    { id: 'vision', label: 'Vision Analyzer', path: '/dashboards/vision' },
  ]

  const handleTabChange = (tabId: string, path: string) => {
    setActiveTab(tabId)
    navigate(path)
  }

  return (
    <div className="space-y-6">
      {/* Subtabs */}
      <div className="bg-white rounded-lg shadow-sm p-1">
        <nav className="flex space-x-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id, tab.path)}
              className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'discovery' && <DiscoveryPage />}
        {activeTab === 'vision' && <VisionAnalyzerPage />}
      </div>
    </div>
  )
}
