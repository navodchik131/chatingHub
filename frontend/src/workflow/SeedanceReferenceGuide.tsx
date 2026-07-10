import { useTranslation } from 'react-i18next'

/** Подсказки по ролям @Image/@Video для Seedance 2.0 (workflow). */

export type SeedanceReferenceGuideVariant = 'motion' | 'compose' | 'video'

export function SeedanceReferenceGuide({
  variant = 'video',
}: {
  variant?: SeedanceReferenceGuideVariant
}) {
  const { t } = useTranslation('workflow')

  const roleRows = [
    { tag: '@Image1', role: t('nodeUi.seedanceGuide.image1Role') },
    { tag: '@Image2+', role: t('nodeUi.seedanceGuide.image2Role') },
    { tag: '@Video1', role: t('nodeUi.seedanceGuide.video1Role') },
  ]

  const motionTips = [
    t('nodeUi.seedanceGuide.motionTip1'),
    t('nodeUi.seedanceGuide.motionTip2'),
    t('nodeUi.seedanceGuide.motionTip3'),
  ]

  return (
    <div className="workflow-seedance-guide nodrag">
      <p className="workflow-seedance-guide__title">{t('nodeUi.seedanceGuide.title')}</p>
      <ul className="workflow-seedance-guide__roles">
        {roleRows.map((row) => (
          <li key={row.tag}>
            <code>{row.tag}</code>
            <span>{row.role}</span>
          </li>
        ))}
      </ul>
      {variant === 'motion' ? (
        <ul className="workflow-seedance-guide__tips">
          {motionTips.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      ) : null}
      {variant === 'compose' ? (
        <p className="workflow-node__hint workflow-node__hint--muted workflow-seedance-guide__foot">
          {t('nodeUi.seedanceGuide.composeFoot')}
        </p>
      ) : null}
      {variant === 'video' ? (
        <p className="workflow-node__hint workflow-node__hint--muted workflow-seedance-guide__foot">
          {t('nodeUi.seedanceGuide.videoFoot')}
        </p>
      ) : null}
    </div>
  )
}
