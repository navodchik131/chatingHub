/**
 * Проверка prod-билда: dist-site не должен содержать legacy mm-os-bridge.
 * Запуск: node scripts/check-prod-build.mjs (после npm run build:site)
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const distSite = path.join(frontendRoot, 'dist-site')
const indexPath = path.join(distSite, 'index.html')

if (!fs.existsSync(indexPath)) {
  console.error('check-prod-build: dist-site/index.html not found — run npm run build:site first')
  process.exit(1)
}

const html = fs.readFileSync(indexPath, 'utf8')
const forbidden = ['mm-os-bridge', 'mm-os-api-full.js', 'MMOS_BRIDGE']
const hits = forbidden.filter((token) => html.includes(token))
if (hits.length) {
  console.error('check-prod-build: legacy mm-os references in dist-site/index.html:', hits.join(', '))
  process.exit(1)
}

const legacyFiles = ['mm-os-bridge.js', 'mm-os-api.js', 'mm-os-api-full.js']
for (const name of legacyFiles) {
  const p = path.join(distSite, name)
  if (fs.existsSync(p)) {
    console.error(`check-prod-build: legacy file copied to dist-site: ${name}`)
    process.exit(1)
  }
}

const size = fs.statSync(indexPath).size
if (size > 20_000) {
  console.error(`check-prod-build: dist-site/index.html too large (${size} bytes) — expected React SPA shell`)
  process.exit(1)
}

console.log(`check-prod-build: OK (index.html ${size} bytes, no mm-os)`)
