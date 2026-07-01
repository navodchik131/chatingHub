/** Подсказки по ролям @Image/@Video для Seedance 2.0 (workflow). */

export type SeedanceReferenceGuideVariant = 'motion' | 'compose' | 'video'

const MOTION_TIPS = [
  'Один человек в кадре, простые движения, до ~15 сек.',
  'Без толпы, драк и сложной хореографии — Seedance это хуже тянет.',
  'Чёткое видео: стабильная камера или понятный tracking.',
]

const ROLE_ROWS: { tag: string; role: string }[] = [
  { tag: '@Image1', role: 'лицо / identity модели' },
  { tag: '@Image2+', role: 'character sheet, одежда, комната (если подключены)' },
  { tag: '@Video1', role: 'только motion + camera — не лицо актёра из видео' },
]

export function SeedanceReferenceGuide({
  variant = 'video',
}: {
  variant?: SeedanceReferenceGuideVariant
}) {
  return (
    <div className="workflow-seedance-guide nodrag">
      <p className="workflow-seedance-guide__title">Seedance 2.0 — роли референсов</p>
      <ul className="workflow-seedance-guide__roles">
        {ROLE_ROWS.map((row) => (
          <li key={row.tag}>
            <code>{row.tag}</code>
            <span>{row.role}</span>
          </li>
        ))}
      </ul>
      {variant === 'motion' ? (
        <ul className="workflow-seedance-guide__tips">
          {MOTION_TIPS.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      ) : null}
      {variant === 'compose' ? (
        <p className="workflow-node__hint workflow-node__hint--muted workflow-seedance-guide__foot">
          Grok пишет промпт с явным MODEL REPLACEMENT: identity из @Image, движение и камера из
          @Video1.
        </p>
      ) : null}
      {variant === 'video' ? (
        <p className="workflow-node__hint workflow-node__hint--muted workflow-seedance-guide__foot">
          Промпт должен явно разделять: кто на экране (@Image) и откуда motion/camera (@Video).
        </p>
      ) : null}
    </div>
  )
}
