/**
 * Regenerate about-service-deck.*.body.html and about-service-deck.css
 * from public/about-service.html (+ .en.html).
 *
 * Usage: node scripts/extract-about-deck.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(__dirname, '..', 'frontend')

function extract(srcPath, bodyOut) {
  const html = fs.readFileSync(srcPath, 'utf8')
  const styleMatch = html.match(/<style>([\s\S]*?)<\/style>/)
  if (!styleMatch) throw new Error(`no <style> in ${srcPath}`)
  let css = styleMatch[1]
  css = css.replace(/\bhtml:not\(/g, 'html.mm-about-active:not(')
  css = css.replace(/\bhtml\[data-motion/g, 'html.mm-about-active[data-motion')
  css = css.replace(/\bhtml\{/g, 'html.mm-about-active{')
  css = css.replace(/\bhtml,/g, 'html.mm-about-active,')
  css = css.replace(/\bbody::/g, '.mm-about-deck::')
  css = css.replace(/\bbody\{/g, '.mm-about-deck{')

  const bodyMatch = html.match(/<body>([\s\S]*?)<script>/)
  if (!bodyMatch) throw new Error(`no <body> in ${srcPath}`)
  fs.writeFileSync(bodyOut, bodyMatch[1].trim())
  return css
}

const ruCss = extract(
  path.join(frontendDir, 'public/about-service.html'),
  path.join(frontendDir, 'public/about-service-deck.ru.body.html'),
)
extract(
  path.join(frontendDir, 'public/about-service.en.html'),
  path.join(frontendDir, 'public/about-service-deck.en.body.html'),
)

fs.writeFileSync(
  path.join(frontendDir, 'src/marketing/about-service-deck.css'),
  `/* About service presentation — scoped for SPA embed */\n${ruCss}`,
)

console.log('about deck fragments updated')
