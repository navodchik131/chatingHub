import { defineConfig } from 'vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))

/** На бою за nginx: VITE_BASE_PATH=/os/ (см. docker-compose.prod.yml). Локально — /. */
const base = process.env.VITE_BASE_PATH || '/'

/** Новый кабинет на базе DesignCode-макета. Старый frontend/ не трогаем. */
export default defineConfig({
  root,
  base,
  publicDir: 'public',
  server: {
    port: 5174,
    strictPort: true,
    // API того же бэкенда, что и у текущего кабинета (docker :18080 или :8080)
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/public-model-image': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8080',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
