import {
  CONVERSATION_CATEGORY_META,
  CONVERSATION_CATEGORY_ORDER,
  countForConversationCategory,
  type ConversationCategory,
  type ConversationCategoryLike,
} from '../conversationCategories'

export function ConversationCategoryTabs({
  active,
  conversations,
  onChange,
}: {
  active: ConversationCategory
  conversations: ConversationCategoryLike[]
  onChange: (category: ConversationCategory) => void
}) {
  return (
    <div className="conv-category-tabs" role="tablist" aria-label="Категории диалогов">
      {CONVERSATION_CATEGORY_ORDER.map((category) => {
        const meta = CONVERSATION_CATEGORY_META[category]
        const count = countForConversationCategory(conversations, category)
        const isActive = category === active
        return (
          <button
            key={category}
            type="button"
            role="tab"
            aria-selected={isActive}
            title={meta.label}
            className={`conv-category-tab${isActive ? ' active' : ''}${
              count > 0 && category !== 'all' ? ' has-items' : ''
            }`}
            onClick={() => onChange(category)}
          >
            <span className="conv-category-tab__label">{meta.label}</span>
            {count > 0 ? (
              <span className="conv-category-tab__count">{count > 99 ? '99+' : count}</span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
