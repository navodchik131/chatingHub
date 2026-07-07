import type { NodeType } from './types'

type Props = {
  type: NodeType
  size?: number
  className?: string
}

const stroke = 'currentColor'

export function NodeIcon({ type, size = 16, className }: Props) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    xmlns: 'http://www.w3.org/2000/svg',
    className,
    'aria-hidden': true as const,
  }

  switch (type) {
    case 'model':
      return (
        <svg {...common}>
          <circle cx="12" cy="8" r="3.5" stroke={stroke} strokeWidth="1.75" />
          <path
            d="M5.5 20c0-3.5 2.9-6 6.5-6s6.5 2.5 6.5 6"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinecap="round"
          />
        </svg>
      )
    case 'realism':
      return (
        <svg {...common}>
          <rect x="4" y="7" width="16" height="12" rx="2" stroke={stroke} strokeWidth="1.75" />
          <circle cx="12" cy="13" r="3" stroke={stroke} strokeWidth="1.75" />
          <path d="M9 7l1.2-2h3.6L15 7" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'selfie':
      return (
        <svg {...common}>
          <rect x="7" y="5" width="10" height="16" rx="2" stroke={stroke} strokeWidth="1.75" />
          <circle cx="12" cy="10" r="2" stroke={stroke} strokeWidth="1.75" />
          <path d="M5 14c2-2 4-3 7-3s5 1 7 3" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'prompt':
      return (
        <svg {...common}>
          <path d="M6 7h12M6 12h9M6 17h11" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'refDescription':
      return (
        <svg {...common}>
          <path
            d="M7 5h10a2 2 0 012 2v10l-3-2H7a2 2 0 01-2-2V7a2 2 0 012-2z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
          <path d="M9 9h6M9 12h4" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'reference':
      return (
        <svg {...common}>
          <rect x="4" y="5" width="16" height="14" rx="2" stroke={stroke} strokeWidth="1.75" />
          <circle cx="9" cy="10" r="1.5" fill={stroke} />
          <path
            d="M4 16l4.5-4.5 3 3L15 11l5 5"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )
    case 'imageGeneration':
      return (
        <svg {...common}>
          <path
            d="M13 3L5 14h6l-1 7 8-11h-6l1-7z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
        </svg>
      )
    case 'preview':
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="14" rx="2" stroke={stroke} strokeWidth="1.75" />
          <circle cx="12" cy="12" r="2.5" stroke={stroke} strokeWidth="1.75" />
          <path d="M3 9h18" stroke={stroke} strokeWidth="1.75" />
        </svg>
      )
    case 'firstFrameGeneration':
      return (
        <svg {...common}>
          <rect x="5" y="4" width="14" height="16" rx="2" stroke={stroke} strokeWidth="1.75" />
          <path d="M9 8h6M9 12h4" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'turnaroundSheet':
      return (
        <svg {...common}>
          <rect x="3" y="6" width="8" height="12" rx="1" stroke={stroke} strokeWidth="1.5" />
          <rect x="13" y="6" width="8" height="5" rx="1" stroke={stroke} strokeWidth="1.5" />
          <rect x="13" y="13" width="8" height="5" rx="1" stroke={stroke} strokeWidth="1.5" />
        </svg>
      )
    case 'motionVideo':
      return (
        <svg {...common}>
          <rect x="3" y="6" width="18" height="12" rx="2" stroke={stroke} strokeWidth="1.75" />
          <path d="M10 10l5 3-5 3V10z" fill={stroke} />
        </svg>
      )
    case 'videoPromptCompose':
      return (
        <svg {...common}>
          <rect x="3" y="6" width="18" height="12" rx="2" stroke={stroke} strokeWidth="1.75" />
          <path d="M10 10l5 3-5 3V10z" fill={stroke} opacity="0.45" />
          <path d="M6 18h8M6 21h11" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'scenarioOutfitChange':
      return (
        <svg {...common}>
          <path
            d="M8 6h8l2 4v10H6V10l2-4z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
          <path d="M8 10h8M10 14h4" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'scenarioMotionVideo':
      return (
        <svg {...common}>
          <rect x="2" y="5" width="13" height="10" rx="1.5" stroke={stroke} strokeWidth="1.75" />
          <path d="M6 8l4 2.5-4 2.5V8z" fill={stroke} />
          <path d="M17 8h5M17 12h5M17 16h3" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    case 'scenarioFirstFrame':
      return (
        <svg {...common}>
          <rect x="6" y="4" width="12" height="16" rx="2" stroke={stroke} strokeWidth="1.75" />
          <circle cx="12" cy="11" r="2.5" stroke={stroke} strokeWidth="1.75" />
        </svg>
      )
    case 'videoGeneration':
      return (
        <svg {...common}>
          <path
            d="M4 7h12v10H4V7zm14 3l4-2v8l-4-2v-4z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
        </svg>
      )
    case 'videoUpscale':
      return (
        <svg {...common}>
          <path
            d="M4 7h12v10H4V7zm14 3l4-2v8l-4-2v-4z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
          <path d="M8 20h8M12 16v4" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      )
    default:
      return null
  }
}

export const NODE_ICON_COLORS: Record<NodeType, string> = {
  model: '#ec4899',
  realism: '#22c55e',
  selfie: '#38bdf8',
  prompt: '#10b981',
  refDescription: '#a855f7',
  reference: '#f59e0b',
  imageGeneration: '#6366f1',
  firstFrameGeneration: '#8b5cf6',
  turnaroundSheet: '#14b8a6',
  motionVideo: '#f97316',
  videoPromptCompose: '#eab308',
  scenarioOutfitChange: '#f472b6',
  scenarioMotionVideo: '#fb923c',
  scenarioFirstFrame: '#a78bfa',
  videoGeneration: '#ef4444',
  videoUpscale: '#06b6d4',
  preview: '#0ea5e9',
}
