import { useEffect } from 'react'
import { WORKFLOW_APP_URL } from '../CabinetRoute'

/** Редirect на отдельное workflow SPA — не in-cabinet stub. */
export default function Workflow() {
  useEffect(() => {
    window.location.replace(WORKFLOW_APP_URL)
  }, [])
  return null
}
