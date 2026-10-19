<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { listCalendarItems, createCalendarItem, updateCalendarItem, deleteCalendarItem, completeCalendarItem } from '../api.js'
import { getAuthToken } from '../auth.js'
import { businessDate, shiftMonth, itemsOnDate, itemStatus, isCompleted, isOverdue, isAnomaly, LEVEL_COLORS } from '../calendarDates.js'
import MonthCalendar from './MonthCalendar.vue'
import GanttChart from './GanttChart.vue'
import TodoPool from './TodoPool.vue'
import EventDialog from './EventDialog.vue'
import HelpButton from './HelpButton.vue'
import HelpDialog from './HelpDialog.vue'
const props = defineProps({ view: { type: String, default: 'calendar' }, disabled: Boolean })
const emit = defineEmits(['navigate', 'busy'])
const today = ref(businessDate()), month = ref(today.value.slice(0,7)), selectedDate = ref(today.value)
const items = ref([]), loading = ref(false), error = ref(''), saving = ref(false), notice = ref('')
const showCompleted = ref(false), helpTopic = ref(''), editor = ref(null), formError = ref('')
const selectedItems = computed(() => itemsOnDate(items.value,selectedDate.value))
const todos = computed(() => items.value.filter(item => !item.due_date && !isCompleted(item)))
const completed = computed(() => items.value.filter(isCompleted))
const overdue = computed(() => items.value.filter(item => isOverdue(item,today.value)))
let alive = true, epoch = 0, timer, initialized = false
const sessionToken = getAuthToken()
function validSession() { return alive && getAuthToken() === sessionToken }
watch(saving, value => emit('busy',value))
async function load() {
  if (!validSession() || saving.value) return
  const batch = ++epoch
  loading.value = true; error.value = ''
  try {
    const all = [], ids = new Set()
    let offset = 0, total = 0, serverToday = today.value
    do {
      const response = await listCalendarItems({ status: 'all', limit: 100, offset })
      if (!validSession() || batch !== epoch) return
      if (!Array.isArray(response.items) || !Number.isInteger(response.total)) throw new Error('日程列表响应格式不正确')
      total = response.total
      if (!response.items.length && offset < total) throw new Error('日程分页未返回完整数据，请刷新重试')
      response.items.forEach(item => { if (!ids.has(item.id)) { all.push(item); ids.add(item.id) } })
      offset += response.items.length
      serverToday = response.today || serverToday
    } while (offset < total)
    items.value = all; today.value = serverToday
    if (!initialized) { month.value = serverToday.slice(0,7); selectedDate.value = serverToday; initialized = true }
  } catch (e) { if (validSession() && batch === epoch) error.value = e.message || '日程加载失败，请重试' }
  finally { if (validSession() && batch === epoch) loading.value = false }
}
function open(item) { if (!saving.value) { editor.value = { item, date: '' }; formError.value = '' } }
function create(date = '') { if (!props.disabled && !saving.value) { editor.value = { item: null, date }; formError.value = '' } }
function close() { if (!saving.value) { editor.value = null; formError.value = '' } }
function replaceItem(item) { const index = items.value.findIndex(row => row.id === item.id); if (index >= 0) items.value.splice(index,1,item); else items.value.unshift(item) }
async function mutate(operation, success) {
  if (props.disabled || saving.value || !validSession()) return
  saving.value = true; formError.value = ''; error.value = ''; notice.value = ''
  try {
    const result = await operation()
    if (!validSession()) return
    success(result); editor.value = null
  } catch (e) { if (validSession()) { if (editor.value) formError.value = e.message; else error.value = e.message } }
  finally { if (alive) saving.value = false }
}
function save(body) {
  const id = editor.value?.item?.id
  mutate(() => id ? updateCalendarItem(id,body) : createCalendarItem(body), result => { replaceItem(result); notice.value = '已保存，日历与待办池已更新。' })
}
function finish(item, completedValue = true) { mutate(() => completeCalendarItem(item.id,completedValue), result => { replaceItem(result); notice.value = completedValue ? '任务已完成，日历提醒已结束。可在已完成列表查看。' : '任务已重新打开。' }) }
function remove() { const id = editor.value.item.id; mutate(() => deleteCalendarItem(id), () => { items.value = items.value.filter(item => item.id !== id); notice.value = '事件已删除。' }) }
function moveMonth(amount) { month.value = shiftMonth(month.value,amount); selectedDate.value = `${month.value}-01` }
function goToday() { month.value = today.value.slice(0,7); selectedDate.value = today.value }
function toggleView() { if (!saving.value) emit('navigate',props.view === 'gantt' ? 'calendar' : 'calendar/gantt') }
function shortcut(event) {
  if (event.defaultPrevented || event.repeat || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.key.toLowerCase() !== 'g' || saving.value || editor.value || helpTopic.value || document.querySelector('[role="dialog"]')) return
  const node = event.target
  if (node?.isContentEditable || ['INPUT','TEXTAREA','SELECT'].includes(node?.tagName)) return
  event.preventDefault(); toggleView()
}
function checkDate() { if (document.visibilityState === 'visible' && businessDate() !== today.value && !saving.value) load() }
onMounted(() => { load(); document.addEventListener('keydown',shortcut); document.addEventListener('visibilitychange',checkDate); window.addEventListener('focus',checkDate); timer = window.setInterval(checkDate,60000) })
onBeforeUnmount(() => { alive = false; epoch++; clearInterval(timer); document.removeEventListener('keydown',shortcut); document.removeEventListener('visibilitychange',checkDate); window.removeEventListener('focus',checkDate); emit('busy',false) })
defineExpose({ refresh: load })
</script>
<template><section class="calendar-panel card" aria-label="日程计划"><header class="main-header"><div><h1>日程计划 <HelpButton label="日历主体" @click="helpTopic='calendar'" /></h1><p class="hint">把待办排进时间里，做完后点击“完成任务”结束提醒。业务时区：Asia/Shanghai。</p></div><button :disabled="loading || saving" @click="load">刷新日程</button></header><p v-if="disabled" class="hint">当前账号可查看日程，没有修改权限。</p><p v-if="error" class="error" role="alert">{{ error }} <button :disabled="loading || saving" @click="load">重试</button></p><p v-if="notice" class="success" role="status">{{ notice }}</p><p v-if="loading" class="hint" role="status">正在加载日程…</p><template v-if="!loading && (!error || initialized)"><div class="toolbar"><div class="month-controls"><button aria-label="上个月" :disabled="saving" @click="moveMonth(-1)">‹</button><h2>{{ month.slice(0,4) }} 年 {{ Number(month.slice(5)) }} 月</h2><button aria-label="下个月" :disabled="saving" @click="moveMonth(1)">›</button><button :disabled="saving" @click="goToday">今天</button></div><div class="view-controls"><button :disabled="saving" class="view-switch" @click="toggleView">{{ view === 'gantt' ? '切换到月历' : '切换到甘特图' }} <kbd>G</kbd></button><HelpButton label="甘特图切换" @click="helpTopic='gantt'" /></div></div><div class="legend" aria-label="紧迫等级图例"><span v-for="n in [5,4,3,2,1]" :key="n"><i :style="{ backgroundColor: LEVEL_COLORS[n] }"></i>{{ n }} 级</span><span><i class="overdue-dot"></i>逾期</span><span class="hint">等级以距离今天的 DDL 计算</span><HelpButton label="手动调整等级" @click="helpTopic='level'" /></div><template v-if="view !== 'gantt'"><MonthCalendar :month="month" :today="today" :selected="selectedDate" :items="items" :disabled="disabled || saving" @create="create" @select="selectedDate=$event" @open="open" /><section class="day-list" aria-label="选中日期的事件"><header><h2>{{ selectedDate }} 的安排</h2><button :disabled="disabled || saving" @click="create(selectedDate)">新建事件</button></header><p v-if="!selectedItems.length" class="empty">无安排</p><ul v-else class="task-list"><li v-for="item in selectedItems" :key="item.id"><button class="item-title" :disabled="saving" @click="open(item)">{{ item.title }}<span class="hint">{{ itemStatus(item,today) }} · DDL {{ item.due_date }}</span></button><button :disabled="disabled || saving" class="finish" @click="finish(item)">完成任务</button></li></ul></section></template><template v-else><label class="completed-toggle"><input v-model="showCompleted" type="checkbox" />显示已完成</label><GanttChart :month="month" :today="today" :items="items" :show-completed="showCompleted" :disabled="saving" @open="open" /></template><section v-if="overdue.length" class="overdue-list" aria-label="逾期事项"><h2>逾期事项 · {{ overdue.length }}</h2><p class="hint">逾期未完成事项始终保留在这里；核对日期或完成任务后结束提醒。</p><ul class="task-list"><li v-for="item in overdue" :key="item.id"><button class="item-title" :disabled="saving" @click="open(item)">{{ item.title }}<span class="hint">DDL {{ item.due_date }}{{ isAnomaly(item) ? ' · 截止日早于开始日，请核对日期' : '' }}</span></button><button class="finish" :disabled="disabled || saving" @click="finish(item)">完成任务</button></li></ul></section><TodoPool :items="todos" :disabled="disabled || saving" @create="create()" @open="open" @complete="finish" @help="helpTopic=$event" /><details class="completed-list"><summary>已完成 · {{ completed.length }}</summary><p v-if="!completed.length" class="hint">还没有已完成的任务。</p><ul v-else class="task-list"><li v-for="item in completed" :key="item.id"><button class="item-title" :disabled="saving" @click="open(item)">{{ item.title }}<span class="hint">已完成{{ item.due_date ? ` · DDL ${item.due_date}` : '' }}</span></button><button :disabled="disabled || saving" @click="finish(item,false)">重新打开任务</button></li></ul></details></template><EventDialog v-if="editor" :key="editor.item?.id || `new-${editor.date}`" :item="editor.item" :date="editor.date" :today="today" :busy="saving" :readonly="disabled" :error="formError" @close="close" @save="save" @complete="finish(editor.item,$event)" @delete="remove" @help="helpTopic=$event" /><HelpDialog v-if="helpTopic" :topic="helpTopic" @close="helpTopic=''" /></section></template>
<style scoped>.calendar-panel{padding:24px;min-width:0;max-width:100%;width:100%;overflow:hidden}.main-header,.toolbar,.month-controls,.view-controls,.day-list header{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.main-header{justify-content:space-between;margin-bottom:18px;align-items:flex-start}h1{font-size:22px;display:flex;align-items:center;gap:8px;margin:0 0 8px}h2{font-size:16px;margin:0}.main-header .hint{margin:0}.toolbar{justify-content:space-between;margin:16px 0}.month-controls h2{min-width:122px;text-align:center}.month-controls button{padding:6px 10px}.legend{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0;font-size:11px}.legend>span{display:inline-flex;align-items:center;gap:5px}.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;border:1px solid #8793a055}.legend .overdue-dot{background:#7f1d1d;border:2px solid #450a0a}.legend .hint{margin:0}kbd{border:1px solid #d2dbea;background:#f5f7fb;padding:1px 4px;border-radius:3px;font-size:10px}.day-list,.overdue-list{margin-top:20px}.day-list header{justify-content:space-between}.empty{padding:20px;background:#f8fafd;border:1px dashed var(--line);text-align:center;color:var(--muted);font-size:13px;margin-top:12px}.task-list{list-style:none;padding:0;margin:10px 0 0}.task-list li{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 0;border-bottom:1px solid var(--line)}.item-title{background:none;border:0;min-width:120px;max-width:100%;padding:0;align-items:flex-start;justify-content:center;text-align:left;flex-direction:column;white-space:pre-wrap;overflow-wrap:anywhere;flex:1}.item-title .hint{font-size:10px;margin:0}.finish{color:#22664d;border-color:#a8d6c2;background:#f0faf5}.overdue-list{border:1px solid #efc6c6;border-radius:8px;padding:14px;background:#fffafa}.overdue-list h2{color:#7f1d1d}.overdue-list .hint{margin:8px 0 0}.completed-list{margin-top:24px;border-top:1px solid var(--line);padding-top:16px}.completed-list summary{cursor:pointer;font-size:14px;font-weight:600;min-height:30px}.completed-toggle{display:flex;align-items:center;gap:6px;font-size:12px;margin:0 0 12px}.completed-toggle input{width:16px;height:16px}.error button{margin-left:8px}.success{font-size:12px}@media(max-width:600px){.calendar-panel{padding:14px}.month-controls{gap:5px}.month-controls h2{min-width:110px;font-size:14px}.toolbar{gap:12px}.legend{gap:8px}.task-list li>button:last-child{font-size:11px;padding:6px 9px}.overdue-list{padding:10px}}
</style>
