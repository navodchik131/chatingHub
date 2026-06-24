import { createContext, useContext } from 'react'
import type { StudioModelOption } from './types'

export const WorkflowModelsContext = createContext<StudioModelOption[]>([])

export function useWorkflowModels(): StudioModelOption[] {
  return useContext(WorkflowModelsContext)
}
