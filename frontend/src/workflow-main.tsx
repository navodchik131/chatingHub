import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './i18n/workflow'
import { WorkflowPage } from './workflow/WorkflowPage'

const basename = (import.meta.env.BASE_URL || '/workflow/').replace(/\/$/, '') || '/workflow'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={basename}>
      <Routes>
        <Route path="/*" element={<WorkflowPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
