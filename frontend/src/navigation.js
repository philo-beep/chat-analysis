export const directorySections = [
  { key: 'tasks', label: '建议待办', icon: 'check' },
  { key: 'questions', label: '待确认事项', icon: 'message' },
  { key: 'screenshots', label: '聊天截图', icon: 'file' },
]

export function sectionFromHash(hash, canViewAdmin = false) {
  const name = hash.replace(/^#\/?/, '')
  if (directorySections.some((item) => item.key === name)) return name
  return name === 'admin' && canViewAdmin ? 'admin' : 'workspace'
}

export function hashForSection(section) {
  return section === 'workspace' ? '#/' : `#/${section}`
}
