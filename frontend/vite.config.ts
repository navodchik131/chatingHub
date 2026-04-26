import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Порт backend для proxy (если uvicorn на 8080 — VITE_BACKEND_PORT=8080 в frontend/.env)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Как в backend/run-dev.ps1 по умолчанию 8080
  const backendPort = env.VITE_BACKEND_PORT || '8080'
  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      // ngrok / другой туннель: иначе «Blocked request. This host is not allowed»
      allowedHosts: true,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
          ws: true,
        },
      },
    },
    preview: {
      host: true,
      port: 4173,
      allowedHosts: true,
    },
  }
})
