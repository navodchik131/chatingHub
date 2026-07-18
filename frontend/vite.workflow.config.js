import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const workflowRoot = path.join(frontendRoot, 'workflow')

/** Production: VITE_WORKFLOW_BASE=/workspace/workflow/ (docker-compose.prod.yml). */
const base = process.env.VITE_WORKFLOW_BASE || '/workspace/workflow/'

export default defineConfig({
  root: workflowRoot,
  base,
  plugins: [react()],
  publicDir: path.join(frontendRoot, 'public'),
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8080',
        changeOrigin: true,
        ws: true,
      },
      '/public-model-image': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: path.join(frontendRoot, 'dist/workflow'),
    emptyOutDir: true,
  },
})
