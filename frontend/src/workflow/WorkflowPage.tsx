import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, getToken } from '../api'
import { hasAllBits, PERM_STUDIO_GENERATE } from '../workspacePermissions'
import { FlowCanvas } from './FlowCanvas'
import { WorkflowModelsContext } from './WorkflowModelsContext'
import type { StudioModelOption } from './types'
import './workflow.css'

interface UserMe {
  permissions_mask?: number
  is_workspace_owner?: boolean
  email?: string
}

export function WorkflowPage() {
  const [gate, setGate] = useState<'loading' | 'ok' | 'denied' | 'anon'>('loading')
  const [models, setModels] = useState<StudioModelOption[]>([])

  useEffect(() => {
    if (!getToken()) {
      setGate('anon')
      return
    }
    void (async () => {
      const meR = await apiFetch('/api/auth/me')
      if (!meR.ok) {
        setGate('anon')
        return
      }
      const me = (await meR.json()) as UserMe
      const owner = Boolean(me.is_workspace_owner)
      const mask = me.permissions_mask ?? 0
      if (!owner && !hasAllBits(mask, PERM_STUDIO_GENERATE)) {
        setGate('denied')
        return
      }
      const modelsR = await apiFetch('/api/studio/models')
      if (modelsR.ok) {
        const raw = (await modelsR.json()) as Array<{ id: number; name: string }>
        setModels(
          Array.isArray(raw)
            ? raw.map((m) => ({ id: m.id, name: m.name }))
            : [],
        )
      }
      setGate('ok')
    })()
  }, [])

  if (gate === 'loading') {
    return (
      <div className="workflow-gate">
        <div className="workflow-gate__card">Загрузка…</div>
      </div>
    )
  }

  if (gate === 'anon') {
    return (
      <div className="workflow-gate">
        <div className="workflow-gate__card">
          <h1>Workflow</h1>
          <p>Нужен вход в аккаунт с доступом к студии.</p>
          <Link className="workflow-gate__link" to="/login">
            Войти
          </Link>
        </div>
      </div>
    )
  }

  if (gate === 'denied') {
    return (
      <div className="workflow-gate">
        <div className="workflow-gate__card">
          <h1>Нет доступа</h1>
          <p>Для workflow нужно право «Генерация промпта и картинок (студия)».</p>
          <Link className="workflow-gate__link" to="/workspace">
            В кабинет
          </Link>
        </div>
      </div>
    )
  }

  if (!models.length) {
    return (
      <div className="workflow-gate">
        <div className="workflow-gate__card">
          <h1>Нет моделей</h1>
          <p>Сначала создайте модель в студии — workflow использует фото из кабинета.</p>
          <Link className="workflow-gate__link" to="/workspace">
            Открыть студию
          </Link>
        </div>
      </div>
    )
  }

  return (
    <WorkflowModelsContext.Provider value={models}>
      <div className="workflow-page">
        <header className="workflow-page__header">
          <div>
            <h1 className="workflow-page__title">Workflow · фаза 0</h1>
            <p className="workflow-page__subtitle">
              Node-редактор · Grok собирает промпт из графа
            </p>
          </div>
          <div className="workflow-page__actions">
            <Link className="workflow-page__btn" to="/workspace">
              ← Студия
            </Link>
          </div>
        </header>
        <div className="workflow-page__body">
          <FlowCanvas />
        </div>
      </div>
    </WorkflowModelsContext.Provider>
  )
}
