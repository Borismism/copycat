import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import DashboardsPage from './pages/DashboardsPage'
import VideoListPage from './pages/VideoListPage'
import ChannelEnforcementPage from './pages/ChannelEnforcementPage'
import { ConfigGeneratorPage } from './pages/ConfigGeneratorPage'

function App() {
  return (
    <AuthProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboards" element={<DashboardsPage />} />
          <Route path="/dashboards/discovery" element={<DashboardsPage />} />
          <Route path="/dashboards/vision" element={<DashboardsPage />} />
          <Route path="/videos" element={<VideoListPage />} />
          <Route path="/channels" element={<ChannelEnforcementPage />} />
          <Route path="/config" element={<ConfigGeneratorPage />} />
        </Routes>
      </Layout>
    </AuthProvider>
  )
}

export default App
