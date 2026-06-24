import { useCallback, useRef, useState } from 'react'

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
  onSelect,
  onCreate,
  onRename,
  onDelete,
  onExport,
  onImport,
}: Props) {
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
    <aside className="workflow-workspaces">
      <div className="workflow-workspaces__head">
        <h2>Проекты</h2>
        <button
          type="button"
          className="workflow-workspaces__add"
          disabled={busy}
          onClick={() => setCreating(true)}
          title="Новый проект"
        >
          +
        </button>
      </div>

      {creating ? (
        <div className="workflow-workspaces__create">
          <input
            className="workflow-workspaces__input"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Название проекта"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') submitCreate()
              if (e.key === 'Escape') setCreating(false)
            }}
          />
          <div className="workflow-workspaces__create-actions">
            <button type="button" className="workflow-workspaces__btn" onClick={submitCreate}>
              Создать
            </button>
            <button
              type="button"
              className="workflow-workspaces__btn workflow-workspaces__btn--ghost"
              onClick={() => setCreating(false)}
            >
              Отмена
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
                onClick={() => onSelect(ws.id)}
                onDoubleClick={() => {
                  setEditingId(ws.id)
                  setEditName(ws.name)
                }}
              >
                {ws.name}
              </button>
            )}
            <button
              type="button"
              className="workflow-workspaces__delete"
              title="Удалить проект"
              disabled={busy}
              onClick={() => {
                if (window.confirm(`Удалить «${ws.name}»?`)) onDelete(ws.id)
              }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>

      <div className="workflow-workspaces__io">
        <button
          type="button"
          className="workflow-workspaces__io-btn"
          disabled={busy || activeId == null}
          onClick={onExport}
          title={activeName ? `Скачать «${activeName}» как JSON` : 'Скачать проект'}
        >
          ↓ JSON
        </button>
        <button
          type="button"
          className="workflow-workspaces__io-btn"
          disabled={busy}
          onClick={() => importRef.current?.click()}
          title="Загрузить проект из JSON"
        >
          ↑ JSON
        </button>
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
