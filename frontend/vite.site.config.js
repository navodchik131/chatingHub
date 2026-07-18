import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const siteRoot = path.join(frontendRoot, 'site')

/** Единое SPA: маркетинг + login + кабинет + admin. */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, frontendRoot, '')
  const backendPort = env.VITE_BACKEND_PORT || '8080'

  return {
    root: siteRoot,
    plugins: [react()],
    publicDir: path.join(frontendRoot, 'public'),
    resolve: {
      alias: {
        '@site': path.join(frontendRoot, 'src'),
      },
    },
    build: {
      outDir: path.join(frontendRoot, 'dist-site'),
      emptyOutDir: true,
    },
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      allowedHosts: true,
      fs: {
        allow: [frontendRoot],
      },
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
          ws: true,
        },
        '/public-model-image': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
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
