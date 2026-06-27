import {
  CHAT_PLATFORM_META,
  type ChatPlatform,
  unreadCountForPlatform,
} from '../chatPlatforms'

interface ConversationLike {
  platform: string
  unread_count?: number
}

export function ConversationPlatformTabs({
  platforms,
  active,
  conversations,
  onChange,
}: {
  platforms: ChatPlatform[]
  active: ChatPlatform
  conversations: ConversationLike[]
  onChange: (platform: ChatPlatform) => void
}) {
  if (platforms.length <= 1) return null

  return (
    <div className="conv-platform-tabs" role="tablist" aria-label="Соцсети">
      {platforms.map((platform) => {
        const meta = CHAT_PLATFORM_META[platform]
        const unread = unreadCountForPlatform(conversations, platform)
        const isActive = platform === active
        return (
          <button
            key={platform}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-label={meta.label}
            title={meta.label}
            className={`conv-platform-tab${isActive ? ' active' : ''}${
              unread > 0 ? ' has-unread' : ''
            }`}
            onClick={() => onChange(platform)}
          >
            <img src={meta.icon} alt="" className="conv-platform-tab__icon" decoding="async" />
            {unread > 0 ? (
              <span className="conv-platform-tab__badge" aria-hidden>
                {unread > 99 ? '99+' : unread}
              </span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
