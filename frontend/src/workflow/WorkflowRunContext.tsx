import { createContext, useContext, type ReactNode } from 'react'

export type WorkflowRunContextValue = {
  workspaceId: number | null
  demoLimited: boolean
}

const WorkflowRunContext = createContext<WorkflowRunContextValue>({
  workspaceId: null,
  demoLimited: false,
})

export function WorkflowRunProvider({
  workspaceId,
  demoLimited,
  children,
}: WorkflowRunContextValue & { children: ReactNode }) {
  return (
    <WorkflowRunContext.Provider value={{ workspaceId, demoLimited }}>
      {children}
    </WorkflowRunContext.Provider>
  )
}

export function useWorkflowRun(): WorkflowRunContextValue {
  return useContext(WorkflowRunContext)
}
