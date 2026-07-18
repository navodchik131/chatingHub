/** Nav visibility by workspace operator permissions (mirrors mm-os-bridge canChat/canStudio/canBilling). */
export function canAccessPage(pageId, me, opRights) {
  if (me?.is_workspace_owner) return true
  const r = opRights || {}
  switch (pageId) {
    case 'overview':
    case 'guide':
      return true
    case 'dialogs':
      return !!r.chat
    case 'images':
    case 'video':
    case 'characters':
    case 'workflow':
      return !!r.studio
    case 'donations':
    case 'billing':
      return !!r.billing
    case 'connections':
      return !!r.keys
    case 'team':
      return false
    default:
      return true
  }
}

export function filterNavGroups(groups, me, opRights) {
  return groups
    .map((grp) => ({
      ...grp,
      items: grp.items.filter((it) => canAccessPage(it.id, me, opRights)),
    }))
    .filter((grp) => grp.items.length > 0)
}

export function filterMobileNavDefs(defs, me, opRights) {
  return defs.filter((mn) => {
    if (mn.more) return true
    if (mn.go === 'overview') return true
    if (mn.go === 'dialogs') return canAccessPage('dialogs', me, opRights)
    if (mn.go === 'images') return canAccessPage('images', me, opRights)
    if (mn.go === 'donations') return canAccessPage('donations', me, opRights)
    return true
  })
}

export function filterMoreItems(items, me, opRights) {
  const filtered = items.filter((mi) => canAccessPage(mi.go, me, opRights))
  if (me?.is_platform_admin) {
    filtered.push({
      label: 'Admin panel',
      desc: 'Users, plans, analytics',
      admin: true,
    })
  }
  return filtered
}
