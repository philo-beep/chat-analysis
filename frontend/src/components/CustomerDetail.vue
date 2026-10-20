<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getCustomer, getCustomerSnapshot, listCustomerSnapshots } from '../api.js'
import { currentUser, sessionVersion } from '../auth.js'
import AppIcon from './AppIcon.vue'

const props = defineProps({ customerId: { type: Number, required: true }, snapshotId: { type: Number, default: null } })
defineEmits(['back', 'snapshot', 'latest'])
const profile = ref(null)
const snapshots = ref([])
const loading = ref(false)
const error = ref('')
const timelineError = ref('')
const snapshotTime = ref('')
const timelineTotal = ref(0)
const timelineLoading = ref(false)
const points = computed(() => profile.value?.communication_points || [])
const hasGuidance = computed(() => !!profile.value?.communication_strategy || points.value.length > 0)
let epoch = 0
onBeforeUnmount(() => { epoch++ })

function formatTime(value) {
  const date = value ? new Date(value) : null
  return !date || Number.isNaN(date.getTime()) ? '时间待确认' : date.toLocaleString('zh-CN', { hour12: false })
}

async function load() {
  const requestEpoch = ++epoch
  const version = sessionVersion.value
  const id = props.customerId
  const selectedSnapshot = props.snapshotId
  const active = () => requestEpoch === epoch && currentUser.value && version === sessionVersion.value
  loading.value = true
  error.value = ''
  timelineError.value = ''
  profile.value = null
  snapshots.value = []
  timelineTotal.value = 0
  timelineLoading.value = false
  const results = await Promise.allSettled([
    selectedSnapshot ? getCustomerSnapshot(id, selectedSnapshot) : getCustomer(id),
    listCustomerSnapshots(id),
  ])
  if (!active()) return
  if (results[0].status === 'fulfilled') {
    const response = results[0].value
    profile.value = response.profile || response
    snapshotTime.value = response.created_at || ''
  } else error.value = `暂时没能读到这份客户资料：${results[0].reason.message}`
  if (results[1].status === 'fulfilled') {
    snapshots.value = results[1].value.items
    timelineTotal.value = results[1].value.total
  }
  else timelineError.value = `更新时间暂时没能读到：${results[1].reason.message}`
  loading.value = false
}

async function loadMoreSnapshots() {
  if (timelineLoading.value) return
  const requestEpoch = epoch
  const version = sessionVersion.value
  const active = () => requestEpoch === epoch && currentUser.value && version === sessionVersion.value
  timelineLoading.value = true
  timelineError.value = ''
  try {
    const response = await listCustomerSnapshots(props.customerId, { offset: snapshots.value.length })
    if (!active()) return
    snapshots.value = [...snapshots.value, ...response.items]
    timelineTotal.value = response.total
  } catch (e) {
    if (active()) timelineError.value = `更早的记录暂时没能读到：${e.message}`
  } finally {
    if (active()) timelineLoading.value = false
  }
}
watch(() => [props.customerId, props.snapshotId], load, { immediate: true })
</script>

<template>
  <section class="customer-detail" aria-label="客户详情">
    <div class="detail-tools"><button type="button" @click="$emit('back')">返回我的客户</button><button :disabled="loading" @click="load"><AppIcon name="refresh" :size="15" />刷新</button></div>
    <p v-if="snapshotId" class="history-banner" role="status">你正在看历史快照<span v-if="snapshotTime"> · {{ formatTime(snapshotTime) }}</span><button type="button" @click="$emit('latest')">回到最新</button></p>
    <p v-if="loading" class="empty" role="status">正在读取客户资料…</p>
    <div v-else-if="error" class="error" role="alert">{{ error }} <button @click="load">重试</button></div>
    <template v-else-if="profile">
      <header class="profile-heading"><h1>{{ profile.display_name || '未知' }}</h1><p>{{ profile.company || '公司待了解' }} · {{ profile.role || '角色待了解' }}</p></header>
      <section class="guidance card" aria-label="沟通指导"><div class="guidance-heading"><AppIcon name="message" :size="24" /><h2>沟通指导</h2></div><template v-if="hasGuidance"><p v-if="profile.communication_strategy" class="strategy">{{ profile.communication_strategy }}</p><ol v-if="points.length"><li v-for="(point, index) in points" :key="index">{{ point }}</li></ol></template><p v-else class="guidance-empty">再聊几次就能给出建议</p></section>
      <div class="profile-grid">
        <section class="card info-card" aria-label="客户基本资料"><h2>基本资料</h2><dl><dt>怎么称呼</dt><dd>{{ profile.display_name || '未知' }}</dd><dt>公司</dt><dd>{{ profile.company || '未知' }}</dd><dt>角色</dt><dd>{{ profile.role || '未知' }}</dd><dt>行业</dt><dd>{{ profile.industry || '未知' }}</dd></dl></section>
        <section class="card info-card"><h2>他关心什么</h2><div v-if="profile.concerns?.length" class="tags"><span v-for="(concern, index) in profile.concerns" :key="index">{{ concern }}</span></div><p v-else class="muted">还需要多了解一些。</p><h3>怎么做决策</h3><p>{{ profile.decision_style || '还需要多了解一些。' }}</p></section>
        <section class="card info-card"><h2>沟通偏好</h2><ul v-if="profile.communication_preferences?.length"><li v-for="(preference, index) in profile.communication_preferences" :key="index">{{ preference }}</li></ul><p v-else class="muted">还没有明确的沟通偏好。</p><h3>下一步跟进</h3><p>{{ profile.next_follow_up && profile.next_follow_up !== '未知' ? profile.next_follow_up : '等待下次沟通补充。' }}</p></section>
        <section class="card info-card"><h2>要避开的雷区</h2><ul v-if="profile.risk_points?.length"><li v-for="(risk, index) in profile.risk_points" :key="index">{{ risk }}</li></ul><p v-else class="muted">目前还没有明确记录。</p></section>
      </div>
      <section class="card timeline" aria-label="画像更新时间线"><h2>每次沟通后的记录</h2><p class="muted">点击一个时间点，回看当时对这位客户的了解。</p><p v-if="timelineError" class="error" role="alert">{{ timelineError }} <button @click="snapshots.length ? loadMoreSnapshots() : load()">重试</button></p><p v-if="!snapshots.length && !timelineError" class="muted">还没有可回看的历史记录。</p><ol v-if="snapshots.length"><li><button class="timeline-link" :aria-pressed="!snapshotId" @click="$emit('latest')">最新画像<span v-if="!snapshotId"> · 正在查看</span></button></li><li v-for="snapshot in snapshots" :key="snapshot.id"><button class="timeline-link" :aria-pressed="snapshotId === snapshot.id" @click="$emit('snapshot', snapshot.id)"><time :datetime="snapshot.created_at">{{ formatTime(snapshot.created_at) }}</time><span v-if="snapshotId === snapshot.id"> · 正在查看</span></button></li></ol><button v-if="snapshots.length < timelineTotal" :disabled="timelineLoading" @click="loadMoreSnapshots">{{ timelineLoading ? '正在读取…' : '查看更早的记录' }}</button></section>
    </template>
  </section>
</template>

<style scoped>
.customer-detail { max-width: 1060px; margin: auto; overflow-wrap: anywhere; }
.detail-tools { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 22px; }
.profile-heading h1 { color: var(--ink); font-size: 28px; margin-bottom: 8px; }
.profile-heading p, .muted { color: var(--muted); font-size: 13px; line-height: 1.8; }
.history-banner { background: #fff5dc; border: 1px solid #e6cf93; border-radius: 9px; padding: 14px; color: #7b5d1e; line-height: 1.8; }
.history-banner button { margin-left: 12px; }
.guidance { background: #e9f2ec; border: 2px solid #86a898; padding: 26px; margin: 24px 0; }
.guidance-heading { display: flex; align-items: center; gap: 10px; color: var(--brand); margin-bottom: 15px; }
h2 { font-size: 17px; color: var(--ink); margin-bottom: 16px; }.guidance h2 { font-size: 22px; margin: 0; }
.strategy { font-size: 19px; line-height: 1.8; color: #244d3e; font-weight: 600; }
li { padding: 4px 0; line-height: 1.9; font-size: 14px; }
ol, ul { margin-bottom: 0; padding-left: 23px; }
.guidance-empty { color: #4e6d5e; line-height: 1.8; margin-bottom: 0; }
.profile-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; }
.info-card { padding: 22px; }.info-card p { font-size: 14px; line-height: 1.9; margin-bottom: 0; }
h3 { font-size: 14px; margin: 22px 0 8px; color: var(--ink); }
dl { display: grid; grid-template-columns: 72px minmax(0,1fr); gap: 12px; font-size: 14px; line-height: 1.8; margin-bottom: 0; }dt { color: var(--muted); }dd { margin: 0; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; }.tags span { background: #edf1e7; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.timeline { padding: 24px; margin-top: 22px; }.timeline ol { list-style: none; border-left: 2px solid #d6e2d7; padding-left: 16px; }.timeline li { padding: 5px 0; }
.timeline-link { justify-content: flex-start; text-align: left; flex-wrap: wrap; height: auto; background: transparent; border-color: transparent; font-weight: 400; }.timeline-link[aria-pressed="true"] { background: var(--soft); color: var(--brand); border-color: #c6d9c8; }
.empty { text-align: center; color: var(--muted); padding: 50px 18px; line-height: 1.8; }
@media(max-width: 600px) { .profile-grid { grid-template-columns: 1fr; }.guidance { padding: 18px; }.strategy { font-size: 17px; }.history-banner button { margin: 10px 0 0; display: flex; }.info-card, .timeline { padding: 18px; } }
</style>
