export type NavIconName =
  | 'overview'
  | 'chat'
  | 'studio'
  | 'model'
  | 'video'
  | 'workflow'

const stroke = 'currentColor'

export function WorkspaceNavIcon({
  name,
  className,
}: {
  name: NavIconName
  className?: string
}) {
  const common = {
    width: 16,
    height: 16,
    viewBox: '0 0 24 24',
    fill: 'none',
    xmlns: 'http://www.w3.org/2000/svg',
    className,
    'aria-hidden': true as const,
  }

  switch (name) {
    case 'overview':
      return (
        <svg {...common}>
          <path
            d="M6 3h5l2 4v14H6V3zm7 8h5l2 4v6h-7v-10z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
        </svg>
      )
    case 'chat':
      return (
        <svg {...common}>
          <path
            d="M4 6a2 2 0 012-2h12a2 2 0 012 2v8a2 2 0 01-2 2H9l-4 4v-4H6a2 2 0 01-2-2V6z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
        </svg>
      )
    case 'studio':
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
    case 'model':
      return (
        <svg {...common}>
          <path
            d="M12 3l2.2 6.8H21l-5.5 4 2.1 6.7L12 16.5 6.4 20.5l2.1-6.7L3 9.8h6.8L12 3z"
            stroke={stroke}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
        </svg>
      )
    case 'video':
      return (
        <svg {...common}>
          <rect x="3" y="6" width="14" height="12" rx="2" stroke={stroke} strokeWidth="1.75" />
          <path d="M17 10l4-2v8l-4-2v-4z" stroke={stroke} strokeWidth="1.75" strokeLinejoin="round" />
        </svg>
      )
    case 'workflow':
      return (
        <svg {...common}>
          <circle cx="6" cy="6" r="2.5" stroke={stroke} strokeWidth="1.75" />
          <circle cx="18" cy="6" r="2.5" stroke={stroke} strokeWidth="1.75" />
          <circle cx="12" cy="18" r="2.5" stroke={stroke} strokeWidth="1.75" />
          <path d="M8.5 6h7M7 8l3.5 8M17 8l-3.5 8" stroke={stroke} strokeWidth="1.75" />
        </svg>
      )
    default:
      return null
  }
}
