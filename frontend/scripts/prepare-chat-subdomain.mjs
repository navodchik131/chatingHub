/**
 * После build:chat:subdomain — manifest и sw.js для base / (chat.model-mate.online).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const out = path.join(frontendRoot, 'dist-chat-root')
const manifestSrc = path.join(frontendRoot, 'chat/public/manifest.subdomain.webmanifest')

if (!fs.existsSync(out)) {
  console.error('prepare-chat-subdomain: dist-chat-root not found — run build:chat:subdomain first')
  process.exit(1)
}

fs.copyFileSync(manifestSrc, path.join(out, 'manifest.webmanifest'))

const swPath = path.join(out, 'sw.js')
let sw = fs.readFileSync(swPath, 'utf8')
sw = sw
  .replaceAll('/chat/', '/')
  .replace('unibox-shell-v1', 'unibox-shell-root-v1')
  .replace("Service-Worker-Allowed \"/chat/\"", 'Service-Worker-Allowed "/"')
fs.writeFileSync(swPath, sw)

console.log('prepare-chat-subdomain: OK')
