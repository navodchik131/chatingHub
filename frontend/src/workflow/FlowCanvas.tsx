import { useCallback, useEffect, useRef } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { WORKFLOW_GRAPH_STORAGE_KEY } from './constants'
import { createNode, REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import { nodeTypes } from './nodes'
import { NodeSidebar } from './NodeSidebar'
import type { AppNode, NodeType } from './types'

function loadStoredGraph(): { nodes: AppNode[]; edges: Edge[] } | null {
  for (const key of [WORKFLOW_GRAPH_STORAGE_KEY, 'mm_workflow_graph_v1']) {
    try {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const parsed = JSON.parse(raw) as { nodes?: AppNode[]; edges?: Edge[] }
      if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) continue
      return { nodes: parsed.nodes, edges: parsed.edges }
    } catch {
      continue
    }
  }
  return null
}

function FlowCanvasInner() {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()
  const stored = loadStoredGraph()

  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>(stored?.nodes ?? [])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(stored?.edges ?? [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      localStorage.setItem(
        WORKFLOW_GRAPH_STORAGE_KEY,
        JSON.stringify({ nodes, edges }),
      )
    }, 400)
    return () => window.clearTimeout(timer)
  }, [nodes, edges])

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((current) => addEdge({ ...connection, animated: true }, current))
    },
    [setEdges],
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const type = event.dataTransfer.getData(REACT_FLOW_DRAG_TYPE) as NodeType
      if (!type || !reactFlowWrapper.current) return
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })
      const newNode = createNode(type, position)
      setNodes((current) => [...current, newNode])
    },
    [screenToFlowPosition, setNodes],
  )

  const clearGraph = useCallback(() => {
    if (!window.confirm('Очистить граф на канвасе?')) return
    setNodes([])
    setEdges([])
    localStorage.removeItem(WORKFLOW_GRAPH_STORAGE_KEY)
  }, [setEdges, setNodes])

  return (
    <div className="workflow-layout">
      <NodeSidebar />
      <div className="workflow-canvas-wrap">
        <div
          ref={reactFlowWrapper}
          style={{ width: '100%', height: '100%' }}
          onDrop={onDrop}
          onDragOver={onDragOver}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={2}
            panOnDrag
            zoomOnScroll
            zoomOnPinch
            deleteKeyCode={['Backspace', 'Delete']}
            style={{ width: '100%', height: '100%' }}
          >
            <Background variant={BackgroundVariant.Lines} gap={24} size={1} color="#27272a" />
            <Controls position="bottom-left" showInteractive />
            <MiniMap
              position="bottom-right"
              nodeColor="#6366f1"
              maskColor="rgb(9, 9, 11, 0.75)"
            />
          </ReactFlow>
        </div>
      </div>
      <button
        type="button"
        className="workflow-page__btn workflow-page__btn--danger"
        style={{ position: 'fixed', bottom: '1rem', left: '17rem', zIndex: 5 }}
        onClick={clearGraph}
      >
        Очистить граф
      </button>
    </div>
  )
}

export function FlowCanvas() {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner />
    </ReactFlowProvider>
  )
}
