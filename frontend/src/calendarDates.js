export const LEVEL_COLORS = { 1: '#D1D5DB', 2: '#94A3B8', 3: '#EAB308', 4: '#EA580C', 5: '#DC2626', overdue: '#7F1D1D', completed: '#6B7280' }
const DAY = 86400000
export function dateNumber(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return NaN
  const [year, month, day] = value.split('-').map(Number)
  const result = new Date(0)
  result.setUTCFullYear(year, month - 1, day)
  result.setUTCHours(0, 0, 0, 0)
  return result.toISOString().slice(0, 10) === value ? result.getTime() / DAY : NaN
}
export function addDays(value, days) { const n = dateNumber(value); return Number.isFinite(n) ? new Date((n + days) * DAY).toISOString().slice(0, 10) : '' }
export function daysBetween(from, to) { return dateNumber(to) - dateNumber(from) }
export function businessDate(value = new Date()) {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date)
  return ['year', 'month', 'day'].map(type => parts.find(p => p.type === type).value).join('-')
}
export function startDate(item) {
  if (Number.isFinite(dateNumber(item.start_date))) return item.start_date
  return businessDate(item.created_at)
}
export function isCompleted(item) { return Boolean(item.completed || item.completed_at) }
export function isOverdue(item, today) { return !isCompleted(item) && Boolean(item.due_date) && item.due_date < today }
export function isAnomaly(item) { return Boolean(item.due_date && startDate(item) && item.due_date < startDate(item)) }
export function urgencyLevel(item, today) {
  if ([1, 2, 3, 4, 5].includes(item.manual_level)) return item.manual_level
  if (!item.due_date) return 1
  const days = daysBetween(today, item.due_date)
  return days <= 2 ? 5 : days <= 4 ? 4 : days <= 6 ? 3 : days <= 8 ? 2 : 1
}
export function itemColor(item, today) { return LEVEL_COLORS[isCompleted(item) ? 'completed' : isOverdue(item, today) ? 'overdue' : urgencyLevel(item, today)] }
export function itemStatus(item, today) { return isCompleted(item) ? '已完成' : isOverdue(item, today) ? '逾期' : `${item.manual_level ? '手动' : '自动'} ${urgencyLevel(item, today)} 级` }
export function itemsOnDate(items, date) {
  return items.filter(item => !isCompleted(item) && item.due_date && (isAnomaly(item) ? date === item.due_date : startDate(item) <= date && date <= item.due_date))
}
export function monthBounds(month) {
  const first = `${month.slice(0, 7)}-01`
  if (!Number.isFinite(dateNumber(first))) throw new Error('月份无效')
  const y = Number(first.slice(0, 4)), m = Number(first.slice(5, 7))
  const next = `${String(m === 12 ? y + 1 : y).padStart(4, '0')}-${String(m === 12 ? 1 : m + 1).padStart(2, '0')}-01`
  return { first, last: addDays(next, -1), next }
}
export function shiftMonth(month, amount) {
  const { first } = monthBounds(month)
  const n = Number(first.slice(0, 4)) * 12 + Number(first.slice(5, 7)) - 1 + amount
  return `${String(Math.floor(n / 12)).padStart(4, '0')}-${String((n % 12 + 12) % 12 + 1).padStart(2, '0')}`
}
export function monthCells(month) {
  const { first } = monthBounds(month)
  const weekday = new Date(dateNumber(first) * DAY).getUTCDay()
  const from = addDays(first, -(weekday + 6) % 7)
  return Array.from({ length: 42 }, (_, i) => addDays(from, i))
}
export function ganttSegments(item, today, from, to) {
  if (!item.due_date || !startDate(item) || isAnomaly(item)) return []
  const parts = [{ from: startDate(item), to: item.due_date, overdue: false }]
  if (isOverdue(item, today)) parts.push({ from: addDays(item.due_date, 1), to: today, overdue: true })
  return parts.map(p => ({ ...p, from: p.from < from ? from : p.from, to: p.to > to ? to : p.to })).filter(p => p.from <= p.to)
}
