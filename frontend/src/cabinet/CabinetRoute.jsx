import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { getToken } from '../api'
import CabinetApp from './App'
import { CabinetDataProvider } from './api/CabinetDataProvider'
import './styles/global.css'

/** Защита /workspace/* — без токена на /login. */
export function CabinetRoute() {
  const location = useLocation()
  if (!getToken()) {
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
])

export function pageFromPathname(pathname) {
  const rest = pathname.replace(/^\/workspace\/?/, '').split('/')[0] || 'overview'
  return CABINET_PAGES.has(rest) ? rest : 'overview'
}

export function pathnameFromPage(page) {
  if (!page || page === 'overview') return '/workspace'
  return `/workspace/${page}`
}

export function useCabinetNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const page = pageFromPathname(location.pathname)

  const go = (nextPage) => () => {
    navigate(pathnameFromPage(nextPage))
  }

  return { page, go, pathname: location.pathname }
}
