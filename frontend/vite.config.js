import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the browser calls /api/... and Vite forwards it to the local
// Python server. In production (S3 + API Gateway) set VITE_API_URL instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
