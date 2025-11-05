import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import DiscoveryPage from './pages/DiscoveryPage'
import RiskAnalyzerPage from './pages/RiskAnalyzerPage'
import VisionAnalyzerPage from './pages/VisionAnalyzerPage'
import VideoListPage from './pages/VideoListPage'
import ChannelListPage from './pages/ChannelListPage'
import { ConfigGeneratorPage } from './pages/ConfigGeneratorPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/discovery" element={<DiscoveryPage />} />
        <Route path="/risk" element={<RiskAnalyzerPage />} />
        <Route path="/vision" element={<VisionAnalyzerPage />} />
        <Route path="/videos" element={<VideoListPage />} />
        <Route path="/channels" element={<ChannelListPage />} />
        <Route path="/config" element={<ConfigGeneratorPage />} />
      </Routes>
    </Layout>
  )
}

export default App
