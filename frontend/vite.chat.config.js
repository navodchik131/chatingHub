import { defineConfig, loadEnv } from 'vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const chatRoot = path.join(frontendRoot, 'chat')

/** Отдельное SPA Unibox — только чаты, base /chat/ */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, frontendRoot, '')
  const backendPort = env.VITE_BACKEND_PORT || '8080'

  return {
    root: chatRoot,
    base: '/chat/',
    // Не копируем весь marketing public (sw.js и т.д.) — только исходники чата
    publicDir: false,
    build: {
      outDir: path.join(frontendRoot, 'dist-chat'),
      emptyOutDir: true,
    },
    server: {
      host: true,
      port: 5174,
      strictPort: true,
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
