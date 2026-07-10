import { useTranslation } from 'react-i18next'
import {
  conversationCategoryLabel,
  conversationCategoryShort,
} from '../i18n/chatLabels'
import {
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
  const { t } = useTranslation('chat')

  return (
    <div className="conv-category-tabs" role="tablist" aria-label={t('categoriesAria')}>
      {CONVERSATION_CATEGORY_ORDER.map((category) => {
        const label = conversationCategoryLabel(category)
        const short = conversationCategoryShort(category)
        const count = countForConversationCategory(conversations, category)
        const isActive = category === active
        return (
          <button
            key={category}
            type="button"
            role="tab"
            aria-selected={isActive}
            title={label}
            className={`conv-category-tab${isActive ? ' active' : ''}${
              count > 0 && category !== 'all' ? ' has-items' : ''
            }`}
            onClick={() => onChange(category)}
          >
            <span className="conv-category-tab__label">{short ?? label}</span>
            {count > 0 ? (
              <span className="conv-category-tab__count">{count > 99 ? '99+' : count}</span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
