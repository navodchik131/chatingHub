import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Порт backend для proxy (если uvicorn на 8080 — VITE_BACKEND_PORT=8080 в frontend/.env)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_BACKEND_PORT || '8000'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  }
})
