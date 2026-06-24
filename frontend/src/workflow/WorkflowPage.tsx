import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, getToken } from '../api'
import { hasAllBits, PERM_STUDIO_GENERATE } from '../workspacePermissions'
import {
  createWorkflowWorkspace,
  deleteWorkflowWorkspace,
  getWorkflowWorkspace,
  listWorkflowWorkspaces,
  saveWorkflowWorkspace,
} from './api'
import { WORKFLOW_GRAPH_STORAGE_KEY } from './constants'
import { FlowCanvas } from './FlowCanvas'
import { hydrateGraphFromServer } from './graphResolver'
import { WorkspaceSidebar, type WorkflowWorkspaceItem } from './WorkspaceSidebar'
import { downloadWorkflowExport, parseWorkflowImport } from './workspaceExport'
import { WorkflowModelsContext } from './WorkflowModelsContext'
import type { ProjectGraph, StudioModelOption } from './types'
import './workflow.css'

interface UserMe {
  permissions_mask?: number
  is_workspace_owner?: boolean
  email?: string
}

function loadLegacyGraph(): ProjectGraph | null {
  for (const key of [WORKFLOW_GRAPH_STORAGE_KEY, 'mm_workflow_graph_v1']) {
    try {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const parsed = JSON.parse(raw) as ProjectGraph
      if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) continue
      return parsed
    } catch {
      continue
    }
  }
  return null
}

export function WorkflowPage() {
  const [gate, setGate] = useState<'loading' | 'ok' | 'denied' | 'anon'>('loading')
  const [models, setModels] = useState<StudioModelOption[]>([])
  const [workspaces, setWorkspaces] = useState<WorkflowWorkspaceItem[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [graph, setGraph] = useState<ProjectGraph>({ nodes: [], edges: [] })
  const [busy, setBusy] = useState(false)
  const saveRef = useRef<number | null>(null)
  const graphRef = useRef(graph)

  graphRef.current = graph

  const refreshWorkspaces = useCallback(async () => {
    const list = await listWorkflowWorkspaces()
    setWorkspaces(list)
    return list
  }, [])

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

      let list = await refreshWorkspaces()
      if (!list.length) {
        const legacy = loadLegacyGraph()
        const created = await createWorkflowWorkspace(
          legacy?.nodes?.length ? 'Мой проект' : 'Новый проект',
        )
        if (legacy?.nodes?.length) {
          await saveWorkflowWorkspace(created.id, { graph: legacy })
          localStorage.removeItem(WORKFLOW_GRAPH_STORAGE_KEY)
          localStorage.removeItem('mm_workflow_graph_v1')
        }
        list = await refreshWorkspaces()
        setActiveId(created.id)
        setGraph(hydrateGraphFromServer(legacy?.nodes?.length ? legacy : created.graph))
      } else {
        setActiveId(list[0].id)
        const ws = await getWorkflowWorkspace(list[0].id)
        setGraph(hydrateGraphFromServer(ws.graph))
      }
      setGate('ok')
    })()
  }, [refreshWorkspaces])

  const selectWorkspace = useCallback(async (id: number) => {
    if (id === activeId) return
    setBusy(true)
    try {
      const ws = await getWorkflowWorkspace(id)
      setActiveId(id)
      setGraph(hydrateGraphFromServer(ws.graph))
    } finally {
      setBusy(false)
    }
  }, [activeId])

  const handleGraphChange = useCallback(
    (next: ProjectGraph) => {
      setGraph(next)
      if (activeId == null) return
      if (saveRef.current) window.clearTimeout(saveRef.current)
      saveRef.current = window.setTimeout(() => {
        void saveWorkflowWorkspace(activeId, { graph: next }).catch(() => {})
      }, 800)
    },
    [activeId],
  )

  const handleCreate = useCallback(
    async (name: string) => {
      setBusy(true)
      try {
        const created = await createWorkflowWorkspace(name)
        await refreshWorkspaces()
        setActiveId(created.id)
        setGraph(hydrateGraphFromServer(created.graph))
      } finally {
        setBusy(false)
      }
    },
    [refreshWorkspaces],
  )

  const handleRename = useCallback(
    async (id: number, name: string) => {
      setBusy(true)
      try {
        await saveWorkflowWorkspace(id, { name })
        await refreshWorkspaces()
      } finally {
        setBusy(false)
      }
    },
    [refreshWorkspaces],
  )

  const handleDelete = useCallback(
    async (id: number) => {
      setBusy(true)
      try {
        await deleteWorkflowWorkspace(id)
        const list = await refreshWorkspaces()
        if (!list.length) {
          const created = await createWorkflowWorkspace('Новый проект')
          await refreshWorkspaces()
          setActiveId(created.id)
          setGraph(hydrateGraphFromServer(created.graph))
          return
        }
        if (activeId === id) {
          const ws = await getWorkflowWorkspace(list[0].id)
          setActiveId(list[0].id)
          setGraph(hydrateGraphFromServer(ws.graph))
        }
      } finally {
        setBusy(false)
      }
    },
    [activeId, refreshWorkspaces],
  )

  const activeWorkspaceName =
    workspaces.find((ws) => ws.id === activeId)?.name ?? 'Проект'

  const handleExport = useCallback(() => {
    if (activeId == null) return
    downloadWorkflowExport(activeWorkspaceName, { nodes: graph.nodes, edges: graph.edges })
  }, [activeId, activeWorkspaceName, graph])

  const handleImport = useCallback(
    async (file: File) => {
      setBusy(true)
      try {
        const text = await file.text()
        const imported = parseWorkflowImport(text)
        const graphClean = hydrateGraphFromServer(imported.graph)

        const replaceCurrent =
          activeId != null &&
          window.confirm(
            `Заменить текущий проект «${activeWorkspaceName}» графом из «${imported.name}»?`,
          )

        if (replaceCurrent && activeId != null) {
          await saveWorkflowWorkspace(activeId, { graph: graphClean })
          setGraph(graphClean)
          return
        }

        const created = await createWorkflowWorkspace(imported.name.slice(0, 120))
        await saveWorkflowWorkspace(created.id, { graph: graphClean })
        await refreshWorkspaces()
        setActiveId(created.id)
        setGraph(graphClean)
      } catch (error) {
        window.alert(error instanceof Error ? error.message : 'Не удалось импортировать JSON')
      } finally {
        setBusy(false)
      }
    },
    [activeId, activeWorkspaceName, refreshWorkspaces],
  )

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
          <p>Сначала создайте модель в студии.</p>
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
            <h1 className="workflow-page__title">Workflow</h1>
            <p className="workflow-page__subtitle">Соберите цепочку и сгенерируйте изображение</p>
          </div>
          <div className="workflow-page__actions">
            <Link className="workflow-page__btn" to="/workspace">
              ← Студия
            </Link>
          </div>
        </header>
        <div className="workflow-page__body">
          <div className="workflow-main">
            <WorkspaceSidebar
              workspaces={workspaces}
              activeId={activeId}
              activeName={activeWorkspaceName}
              busy={busy}
              onSelect={(id) => void selectWorkspace(id)}
              onCreate={(name) => void handleCreate(name)}
              onRename={(id, name) => void handleRename(id, name)}
              onDelete={(id) => void handleDelete(id)}
              onExport={handleExport}
              onImport={(file) => void handleImport(file)}
            />
            {activeId != null ? (
              <FlowCanvas
                key={activeId}
                workspaceId={activeId}
                initialGraph={graph}
                onGraphChange={handleGraphChange}
              />
            ) : null}
          </div>
        </div>
      </div>
    </WorkflowModelsContext.Provider>
  )
}
