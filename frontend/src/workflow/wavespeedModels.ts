export interface WaveSpeedModelDefinition {
  id: string
  label: string
  provider: string
  description: string
}

export const WAVESPEED_MODELS: WaveSpeedModelDefinition[] = [
  {
    id: 'nano-banana-2',
    label: 'Nano Banana 2',
    provider: 'Google',
    description: 'Быстрая генерация Google Nano Banana 2',
  },
  {
    id: 'nano-banana-pro',
    label: 'Nano Banana Pro',
    provider: 'Google',
    description: 'Gemini 3.0 Pro Image, до 4K',
  },
  {
    id: 'wan-2.7',
    label: 'Wan 2.7',
    provider: 'Alibaba',
    description: 'Wan 2.7 image edit',
  },
  {
    id: 'gpt-image-2',
    label: 'GPT Image 2',
    provider: 'OpenAI',
    description: 'OpenAI GPT Image 2 edit',
  },
]

export const DEFAULT_WAVESPEED_MODEL_ID = 'wan-2.7'
