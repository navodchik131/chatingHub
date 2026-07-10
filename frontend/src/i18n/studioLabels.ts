import i18n, { STUDIO_NS } from './index'

export type StudioJobMode =
  | 'model_scene'
  | 'model'
  | 'photo_edit'
  | 'no_face'
  | 'face_swap'
  | 'grok_compose'

export type StudioModelImageKind = 'turnaround' | 'face' | 'body' | 'genitals' | 'other'

export const STUDIO_IMAGE_MODE_IDS: StudioJobMode[] = [
  'model_scene',
  'grok_compose',
  'model',
  'photo_edit',
  'no_face',
]

export const STUDIO_MODEL_IMAGE_KIND_VALUES: StudioModelImageKind[] = [
  'turnaround',
  'face',
  'body',
  'genitals',
  'other',
]

export function studioImageModeLabel(id: StudioJobMode): string {
  return i18n.t(`modes.${id}`, { ns: STUDIO_NS, defaultValue: id })
}

export function studioModelImageKindLabel(kind: StudioModelImageKind): string {
  return i18n.t(`modelImageKinds.${kind}`, { ns: STUDIO_NS, defaultValue: kind })
}
