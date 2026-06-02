import type { ReactNode } from 'react'
import { WAVESPEED_REF_URL } from './planCatalog'

const WS_HOST_SPLIT = /(wavespeed\.ai)/gi
const WS_HOST_EXACT = /^wavespeed\.ai$/i

/** Текст с «wavespeed.ai» → кликабельная реферальная ссылка. */
export function renderWithWavespeedRef(text: string): ReactNode {
  const parts = text.split(WS_HOST_SPLIT)
  if (parts.length === 1) return text
  return parts.map((part, i) =>
    WS_HOST_EXACT.test(part) ? (
      <a key={i} href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
        {part}
      </a>
    ) : (
      part
    ),
  )
}
