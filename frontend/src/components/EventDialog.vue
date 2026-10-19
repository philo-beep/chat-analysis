<script setup>
import { ref } from 'vue'
import CalendarDialog from './CalendarDialog.vue'
import HelpButton from './HelpButton.vue'
import { startDate, itemStatus } from '../calendarDates.js'
const props = defineProps({ item: { type: Object, default: null }, date: { type: String, default: '' }, today: String, busy: Boolean, readonly: Boolean, error: String })
const emit = defineEmits(['close', 'save', 'complete', 'delete', 'help'])
const title = ref(props.item?.title || '')
const notes = ref(props.item?.notes || '')
const due = ref(props.item?.due_date || props.date)
const level = ref(props.item?.manual_level ?? '')
const localError = ref('')
const requireDue = !props.item && Boolean(props.date)
function save() {
  localError.value = ''
  if (!title.value.trim()) { localError.value = '请填写标题'; return }
  emit('save', { title: title.value.trim(), notes: notes.value, due_date: due.value || null, manual_level: level.value === '' ? null : Number(level.value) })
}
function remove() { if (window.confirm(`确定删除“${props.item.title}”？删除后无法恢复。`)) emit('delete') }
</script>
<template><CalendarDialog :title="item ? '事件详情' : date ? '新建事件' : '新增待办'" :busy="busy" @close="!busy && $emit('close')"><form @submit.prevent="save"><div class="context"><span v-if="item">{{ itemStatus(item, today) }} · #{{ item.id }}</span><HelpButton label="事件创建与结束" @click="$emit('help', 'event')" /></div><label>标题 <span class="required">*</span><input v-model="title" maxlength="200" required :disabled="busy || readonly" placeholder="要完成什么事情" /></label><label>DDL 截止日期 <span v-if="requireDue" class="required">*</span><input v-model="due" type="date" :required="requireDue" :disabled="busy || readonly" /><span class="hint">{{ requireDue ? '创建后开始日由后端提供，无需填写。' : '不设置截止日期时，事项会保留在待办池。' }}</span></label><p v-if="item" class="hint">开始日：{{ startDate(item) || '暂无' }}（{{ item.start_date ? 'AI 返回' : '创建日兜底' }}）</p><div class="label-row"><label for="calendar-level">紧迫等级</label><HelpButton label="手动调整等级" @click="$emit('help', 'level')" /></div><div class="level-row"><select id="calendar-level" v-model="level" :disabled="busy || readonly"><option value="">自动</option><option v-for="n in 5" :key="n" :value="n">{{ n }} 级{{ n === 5 ? '（最急）' : n === 1 ? '（最缓）' : '' }}</option></select><button type="button" :disabled="busy || readonly || level === ''" @click="level = ''">恢复自动</button></div><p class="hint">恢复自动后，点击保存生效。逾期样式优先显示。</p><label>备注<textarea v-model="notes" maxlength="5000" rows="3" :disabled="busy || readonly" /></label><p v-if="error || localError" class="error" role="alert">{{ error || localError }}</p><div class="actions"><button class="primary" type="submit" :disabled="busy || readonly">{{ busy ? '正在保存…' : '保存' }}</button><button type="button" :disabled="busy" @click="$emit('close')">取消</button></div><div v-if="item" class="completion"><button type="button" :disabled="busy || readonly" class="finish" @click="$emit('complete', !item.completed)">{{ item.completed ? '重新打开任务' : '完成任务' }}</button><button type="button" class="delete" :disabled="busy || readonly" @click="remove">删除事件</button><p class="hint">完成后停止日历提醒，记录保留在“已完成”。</p></div></form></CalendarDialog></template>
<style scoped>label{display:block;font-size:13px;margin:14px 0 6px}label input,label textarea{margin-top:6px}.context,.label-row,.level-row,.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.context{justify-content:space-between;font-size:12px;color:var(--muted)}.label-row{margin-top:14px}.label-row label{margin:0}.level-row{margin-top:8px}.level-row select{flex:1;padding:10px;border:1px solid var(--line);border-radius:7px;min-width:100px;background:white;color:var(--ink)}.actions{margin-top:20px}.required,.delete{color:#b91c1c}.completion{border-top:1px solid var(--line);margin-top:20px;padding-top:16px;display:flex;flex-wrap:wrap;gap:10px}.completion p{width:100%;margin:0}.finish{color:#22664d;border-color:#a8d6c2;background:#f0faf5}.hint{display:block;margin-top:6px}</style>
