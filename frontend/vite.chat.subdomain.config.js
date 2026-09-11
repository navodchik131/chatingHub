import { defineConfig, loadEnv } from 'vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const chatRoot = path.join(frontendRoot, 'chat')

/** Unibox для chat.model-mate.online — base /, отдельный dist-chat-root */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, frontendRoot, '')
  const backendPort = env.VITE_BACKEND_PORT || '8080'

  return {
    root: chatRoot,
    base: '/',
    publicDir: path.join(chatRoot, 'public'),
    build: {
      outDir: path.join(frontendRoot, 'dist-chat-root'),
      emptyOutDir: true,
    },
    server: {
      host: true,
      port: 5175,
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
