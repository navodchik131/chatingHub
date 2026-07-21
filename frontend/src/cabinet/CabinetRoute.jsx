import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AuthCheckingScreen } from '../auth/AuthCheckingScreen'
import { useAuthSessionGate } from '../auth/useAuthSessionGate'
import CabinetApp from './App'
import { CabinetDataProvider } from './api/CabinetDataProvider'
import './styles/global.css'

/** Защита /workspace/* — без валидной сессии на /login. */
export function CabinetRoute() {
  const location = useLocation()
  const session = useAuthSessionGate()

  if (session === 'checking') {
    return <AuthCheckingScreen variant="cabinet" />
  }

  if (session === 'anonymous') {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  return (
    <CabinetDataProvider>
      <CabinetApp />
    </CabinetDataProvider>
  )
}

/** Синхронизация state.page кабинета с URL /workspace/:page */
export const CABINET_PAGES = new Set([
  'overview',
  'guide',
  'dialogs',
  'images',
  'video',
  'characters',
  'donations',
  'billing',
  'connections',
  'team',
  'newOperator',
  'workflow',
  'support',
  'profile',
])

export function pageFromPathname(pathname) {
  const rest = pathname.replace(/^\/workspace\/?/, '').split('/')[0] || 'overview'
  return CABINET_PAGES.has(rest) ? rest : 'overview'
}

/** Отдельная сборка workflow SPA (не страница кабинета). */
export const WORKFLOW_APP_URL = '/workspace/workflow/'

export function pathnameFromPage(page) {
  if (!page || page === 'overview') return '/workspace'
  if (page === 'workflow') return WORKFLOW_APP_URL
  return `/workspace/${page}`
}

export function useCabinetNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const page = pageFromPathname(location.pathname)

  const go = (nextPage) => () => {
    if (nextPage === 'workflow') {
      window.location.assign(WORKFLOW_APP_URL)
      return
    }
    navigate(pathnameFromPage(nextPage))
  }

  return { page, go, pathname: location.pathname }
}
