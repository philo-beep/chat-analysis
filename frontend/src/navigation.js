export const directorySections = [
  { key: 'tasks', label: '建议待办', icon: 'check' },
  { key: 'questions', label: '待确认事项', icon: 'message' },
  { key: 'screenshots', label: '聊天截图', icon: 'file' },
]

export function routeFromHash(hash, canViewAdmin = false) {
  const name = hash.replace(/^#\/?/, '')
  const customer = /^customers\/([1-9]\d*)(?:\/snapshots\/([1-9]\d*))?$/.exec(name)
  if (customer && Number.isSafeInteger(Number(customer[1])) && (!customer[2] || Number.isSafeInteger(Number(customer[2])))) {
    return { section: 'customers', recordId: null, customerId: Number(customer[1]), snapshotId: customer[2] ? Number(customer[2]) : null }
  }
  if (name === 'customers') return { section: 'customers', recordId: null, customerId: null, snapshotId: null }
  const scoped = /^records\/([1-9]\d*)\/(tasks|questions|screenshots)$/.exec(name)
  if (scoped && Number.isSafeInteger(Number(scoped[1]))) return { section: scoped[2], recordId: Number(scoped[1]) }
  if (directorySections.some((item) => item.key === name)) return { section: name, recordId: null }
  if (name === 'calendar' || name === 'calendar/gantt') return { section: name, recordId: null }
  return { section: name === 'admin' && canViewAdmin ? 'admin' : 'workspace', recordId: null }
}

export function sectionFromHash(hash, canViewAdmin = false) {
  return routeFromHash(hash, canViewAdmin).section
}

export function hashForSection(section, recordId = null, customerId = null, snapshotId = null) {
  if (section === 'customers' && Number.isSafeInteger(customerId) && customerId > 0) {
    return `#/customers/${customerId}` + (Number.isSafeInteger(snapshotId) && snapshotId > 0 ? `/snapshots/${snapshotId}` : '')
  }
  if (directorySections.some((item) => item.key === section) && Number.isSafeInteger(recordId) && recordId > 0) return `#/records/${recordId}/${section}`
  return section === 'workspace' ? '#/' : `#/${section}`
}
