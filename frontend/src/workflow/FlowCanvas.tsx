import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Background,
  BackgroundVariant,
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
import { NodePaletteDock } from './NodePaletteDock'
import { WorkflowCanvasControls } from './WorkflowCanvasControls'
import { serializeGraph } from './graphResolver'
import { createNode, REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import { nodeTypes } from './nodes'
import type { AppNode, NodeType, ProjectGraph } from './types'

type Props = {
  workspaceId: number
  initialGraph: ProjectGraph
  onGraphChange: (graph: ProjectGraph) => void
}

function FlowCanvasInner({ workspaceId, initialGraph, onGraphChange }: Props) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition, zoomIn, zoomOut, fitView } = useReactFlow()
  const saveTimerRef = useRef<number | null>(null)
  const loadedWorkspaceRef = useRef<number | null>(null)
  const [nodesLocked, setNodesLocked] = useState(false)

  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>(initialGraph.nodes as AppNode[])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialGraph.edges)

  // Подгружать граф только при смене проекта — не после автосохранения (иначе теряется previewUrl).
  useEffect(() => {
    if (loadedWorkspaceRef.current === workspaceId) return
    loadedWorkspaceRef.current = workspaceId
    setNodes((initialGraph.nodes as AppNode[]) ?? [])
    setEdges(initialGraph.edges ?? [])
  }, [workspaceId, initialGraph, setEdges, setNodes])

  useEffect(() => {
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    saveTimerRef.current = window.setTimeout(() => {
      onGraphChange(serializeGraph(nodes, edges))
    }, 600)
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    }
  }, [nodes, edges, onGraphChange])

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((current) => addEdge({ ...connection, animated: false }, current))
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

  return (
    <div className="workflow-layout">
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
            nodesDraggable={!nodesLocked}
            nodesConnectable={!nodesLocked}
            elementsSelectable={!nodesLocked}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={2}
            panOnDrag
            zoomOnScroll
            zoomOnPinch
            edgesFocusable={false}
            deleteKeyCode={nodesLocked ? null : ['Backspace', 'Delete']}
            defaultEdgeOptions={{ animated: false }}
            style={{ width: '100%', height: '100%' }}
          >
            <Background variant={BackgroundVariant.Lines} gap={24} size={1} color="#27272a" />
            <WorkflowCanvasControls
              locked={nodesLocked}
              onZoomIn={() => zoomIn({ duration: 150 })}
              onZoomOut={() => zoomOut({ duration: 150 })}
              onFitView={() => {
                void fitView({ padding: 0.2, duration: 200 })
              }}
              onToggleLock={() => setNodesLocked((v) => !v)}
            />
            <MiniMap
              position="bottom-right"
              nodeColor="#6366f1"
              maskColor="rgb(9, 9, 11, 0.75)"
            />
          </ReactFlow>
        </div>
      </div>
      <NodePaletteDock />
    </div>
  )
}

export function FlowCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner {...props} />
    </ReactFlowProvider>
  )
}
