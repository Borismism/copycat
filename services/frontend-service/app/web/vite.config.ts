import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true,  // Required for Docker volume mounts
      interval: 300,
    },
    hmr: {
      host: 'localhost',
    },
    proxy: {
      '/api': {
        target: 'http://api-service:8080',  // Docker service name
        changeOrigin: true,
      },
    },
  },
})
