import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface WorkflowWorkspaceItem {
  id: number
  name: string
  updated_at: string
}

type Props = {
  workspaces: WorkflowWorkspaceItem[]
  activeId: number | null
  activeName: string
  busy: boolean
  demoLimited?: boolean
  mobileOpen?: boolean
  onClose?: () => void
  onSelect: (id: number) => void
  onCreate: (name: string) => void
  onRename: (id: number, name: string) => void
  onDelete: (id: number) => void
  onExport: () => void
  onImport: (file: File) => void
}

export function WorkspaceSidebar({
  workspaces,
  activeId,
  activeName,
  busy,
  demoLimited = false,
  mobileOpen = false,
  onClose,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  onExport,
  onImport,
}: Props) {
  const { t } = useTranslation('workflow')
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const importRef = useRef<HTMLInputElement>(null)

  const submitCreate = useCallback(() => {
    const name = newName.trim()
    if (!name) return
    onCreate(name)
    setNewName('')
    setCreating(false)
  }, [newName, onCreate])

  const submitRename = useCallback(() => {
    if (editingId == null) return
    const name = editName.trim()
    if (!name) return
    onRename(editingId, name)
    setEditingId(null)
    setEditName('')
  }, [editName, editingId, onRename])

  return (
    <aside className={`workflow-workspaces${mobileOpen ? ' is-open' : ''}`}>
      <div className="workflow-workspaces__head">
        <h2>{t('sidebar.projects')}</h2>
        <div className="workflow-workspaces__head-actions">
          {!demoLimited ? (
            <button
              type="button"
              className="workflow-workspaces__add"
              disabled={busy}
              onClick={() => setCreating(true)}
              title={t('sidebar.newProject')}
            >
              +
            </button>
          ) : null}
          {onClose ? (
            <button
              type="button"
              className="workflow-workspaces__close"
              aria-label={t('page.closeProjectsAria')}
              onClick={onClose}
            >
              ×
            </button>
          ) : null}
        </div>
      </div>

      {creating ? (
        <div className="workflow-workspaces__create">
          <input
            className="workflow-workspaces__input"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t('sidebar.projectNamePlaceholder')}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') submitCreate()
              if (e.key === 'Escape') setCreating(false)
            }}
          />
          <div className="workflow-workspaces__create-actions">
            <button type="button" className="workflow-workspaces__btn" onClick={submitCreate}>
              {t('sidebar.create')}
            </button>
            <button
              type="button"
              className="workflow-workspaces__btn workflow-workspaces__btn--ghost"
              onClick={() => setCreating(false)}
            >
              {t('sidebar.cancel')}
            </button>
          </div>
        </div>
      ) : null}

      <ul className="workflow-workspaces__list">
        {workspaces.map((ws) => (
          <li key={ws.id} className="workflow-workspaces__item">
            {editingId === ws.id ? (
              <input
                className="workflow-workspaces__input"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                autoFocus
                onBlur={submitRename}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') submitRename()
                  if (e.key === 'Escape') setEditingId(null)
                }}
              />
            ) : (
              <button
                type="button"
                className={`workflow-workspaces__link${activeId === ws.id ? ' is-active' : ''}`}
                onClick={() => {
                  onSelect(ws.id)
                  onClose?.()
                }}
                onDoubleClick={() => {
                  if (demoLimited) return
                  setEditingId(ws.id)
                  setEditName(ws.name)
                }}
              >
                {ws.name}
              </button>
            )}
            {!demoLimited && editingId !== ws.id ? (
              <button
                type="button"
                className="workflow-workspaces__edit"
                title={t('sidebar.rename')}
                aria-label={t('sidebar.renameProject', { name: ws.name })}
                onClick={() => {
                  setEditingId(ws.id)
                  setEditName(ws.name)
                }}
              >
                ✎
              </button>
            ) : null}
            {!demoLimited ? (
              <button
                type="button"
                className="workflow-workspaces__delete"
                title={t('sidebar.delete')}
                disabled={busy}
                onClick={() => {
                  if (window.confirm(t('sidebar.deleteConfirm', { name: ws.name }))) onDelete(ws.id)
                }}
              >
                ×
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      <div className="workflow-workspaces__io">
        <button
          type="button"
          className="workflow-workspaces__io-btn"
          disabled={busy || activeId == null}
          onClick={onExport}
          title={
            activeName
              ? t('sidebar.exportProject', { name: activeName })
              : t('sidebar.exportFallback')
          }
        >
          ↓ JSON
        </button>
        {!demoLimited ? (
          <button
            type="button"
            className="workflow-workspaces__io-btn"
            disabled={busy}
            onClick={() => importRef.current?.click()}
            title={t('sidebar.import')}
          >
            ↑ JSON
          </button>
        ) : null}
        <input
          ref={importRef}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onImport(file)
            e.target.value = ''
          }}
        />
      </div>
    </aside>
  )
}
