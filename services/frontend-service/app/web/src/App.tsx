import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import DiscoveryPage from './pages/DiscoveryPage'
import ChannelListPage from './pages/ChannelListPage'
import VideoListPage from './pages/VideoListPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/discovery" element={<DiscoveryPage />} />
        <Route path="/channels" element={<ChannelListPage />} />
        <Route path="/videos" element={<VideoListPage />} />
      </Routes>
    </Layout>
  )
}

export default App
