<!-- 页面总入口，A 负责 -->
<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ChatInput from './components/ChatInput.vue'
import RecordList from './components/RecordList.vue'
import ResultPanel from './components/ResultPanel.vue'
import AppIcon from './components/AppIcon.vue'
import LoginPanel from './components/LoginPanel.vue'
import AdminPanel from './components/AdminPanel.vue'
import SidebarDirectories from './components/SidebarDirectories.vue'
import TaskList from './components/TaskList.vue'
import QuestionList from './components/QuestionList.vue'
import ScreenshotList from './components/ScreenshotList.vue'
import CalendarPanel from './components/CalendarPanel.vue'
import { directorySections, hashForSection, routeFromHash, sectionFromHash } from './navigation.js'
import { buildRecordViews, loadRecordDetails } from './recordViews.js'
import { analyze, getRecord, listRecords, deleteRecord, getCurrentUser, logout, trackPageView, importCalendarTask } from './api.js'
import { currentUser, sessionVersion, getAuthToken, establishSession, restoreSessionUser, clearSession } from './auth.js'

const inputArea = ref(null)
async function focusChatInput() {
  await nextTick()
  const input = inputArea.value?.querySelector('textarea')
  input?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' })
  input?.focus({ preventScroll: true })
}
const records = ref([])
const calendarPanel = ref(null)
const result = ref(null)
const loading = ref(false)
const error = ref('')
const historyError = ref('')
const historyNotice = ref('')
const recordId = ref(null)
const recordsLoading = ref(false)
const originalText = ref('')
const sourceImage = ref('')
const panelBusy = ref(false)
const authReady = ref(false)
const authChecking = ref(false)
const notice = ref('')
const restoreFailed = ref(false)
const loggingOut = ref(false)
const section = ref(sectionFromHash(window.location.hash))
const directoryRecordId = ref(routeFromHash(window.location.hash).recordId)
const scopeMode = ref(directoryRecordId.value || section.value === 'workspace' ? 'current' : 'all')
const scopedRecord = ref(null)
const scopedLoading = ref(false)
const scopedError = ref('')
let scopedEpoch = 0
const canViewAdmin = computed(() => currentUser.value?.permissions?.includes('admin:stats'))
const canWrite = computed(() => currentUser.value?.permissions?.includes('records:write') === true)
const isCalendar = computed(() => section.value === 'calendar' || section.value === 'calendar/gantt')
const sectionTitle = computed(() => directorySections.find((item) => item.key === section.value)?.label || (isCalendar.value ? '日程计划' : section.value === 'admin' ? '网站后台统计' : '需求工作台'))
const calendarImportMessage = ref('')
const calendarImportError = ref('')
const directoryComponent = computed(() => ({ tasks: TaskList, questions: QuestionList, screenshots: ScreenshotList })[section.value])
const directoryRecords = ref([])
const directoryLoading = ref(false)
const directoryLoaded = ref(false)
const directoryError = ref('')
const directoryFailures = ref([])
const directoryProgress = ref(0)
const workspaceReady = ref(false)
const directoryCache = new Map()
let directoryEpoch = 0
const recordViews = computed(() => buildRecordViews(directoryRecords.value))
const scopedViews = computed(() => buildRecordViews(scopedRecord.value ? [scopedRecord.value] : []))
const activeViews = computed(() => directoryRecordId.value ? scopedViews.value : recordViews.value)
const shortcutRecordId = computed(() => directoryRecordId.value || recordId.value)
const shortcutRecordTitle = computed(() => scopedRecord.value?.title || records.value.find((item) => item.id === shortcutRecordId.value)?.title || (shortcutRecordId.value ? `记录 #${shortcutRecordId.value}` : '尚未选择聊天'))
const directoryCounts = computed(() => {
  let views
  if (scopeMode.value === 'current') {
    if (directoryRecordId.value) {
      if (!scopedRecord.value || scopedLoading.value || scopedError.value) return null
      views = scopedViews.value
    } else {
      if (!recordId.value || !result.value) return null
      views = buildRecordViews([{ id: recordId.value, result: result.value, source_image: sourceImage.value }])
    }
  } else {
    if (!directoryLoaded.value || directoryFailures.value.length) return null
    views = recordViews.value
  }
  return Object.fromEntries(Object.entries(views).map(([key, items]) => [key, items.length]))
})

function navigate(next, targetId = null) {
  if (loading.value || panelBusy.value) return
  const route = routeFromHash(hashForSection(next, targetId), canViewAdmin.value)
  section.value = route.section
  directoryRecordId.value = route.recordId
  scopeMode.value = route.recordId || route.section === 'workspace' ? 'current' : 'all'
  const hash = hashForSection(section.value, directoryRecordId.value)
  if (window.location.hash !== hash) window.location.hash = hash
}

function navigateDirectory(next) {
  if (next === 'calendar' || next === 'workspace') return navigate(next)
  if (scopeMode.value === 'current' && !shortcutRecordId.value) return
  navigate(next, scopeMode.value === 'current' ? shortcutRecordId.value : null)
}

async function addSuggestionToCalendar(item) {
  if (!canWrite.value || loading.value || panelBusy.value) return
  const version = sessionVersion.value
  panelBusy.value = true
  calendarImportMessage.value = ''
  calendarImportError.value = ''
  try {
    const task = await importCalendarTask({ record_id: item.recordId, task_index: item.taskIndex, expected_text: item.text })
    if (isCurrent(version)) calendarImportMessage.value = task.completed
      ? `「${task.title}」已存在于日程计划的已完成列表，可在那里重新打开。`
      : task.due_date ? `「${task.title}」已排期，可在日程计划查看；重复点击不会重复创建。`
        : `「${task.title}」已加入日程计划，可在待办池排期；重复点击不会重复创建。`
  } catch (e) {
    if (isCurrent(version)) calendarImportError.value = `加入待办池失败：${e.message}`
  } finally {
    if (isCurrent(version)) panelBusy.value = false
  }
}

async function removeHistoryRecord(record) {
  if (!canWrite.value || loading.value || panelBusy.value) return
  const confirmed = window.confirm(
    `删除聊天记录“${record.title || '未命名'}”后，将同时删除你个人日历中从这份聊天同步的事项，包括待办池、已排期和已完成事项。手工创建的日历事项不受影响，其他用户日历中的事项也不受影响。删除后无法恢复。\n\n确定继续删除吗？`,
  )
  if (!confirmed) return
  const version = sessionVersion.value
  panelBusy.value = true
  historyError.value = ''
  historyNotice.value = ''
  try {
    const response = await deleteRecord(record.id)
    if (!isCurrent(version)) return
    records.value = records.value.filter((item) => item.id !== record.id)
    directoryRecords.value = directoryRecords.value.filter((item) => item.id !== record.id)
    directoryCache.delete(record.id)
    if (scopedRecord.value?.id === record.id) scopedRecord.value = null
    if (recordId.value === record.id) {
      recordId.value = null
      result.value = null
      originalText.value = ''
      sourceImage.value = ''
      try { localStorage.removeItem(`keyoushu.lastRecordId.${currentUser.value.id}`) } catch { /* 缓存不可用不影响删除。 */ }
    }
    if (directoryRecordId.value === record.id) {
      directoryRecordId.value = null
      section.value = 'workspace'
      scopeMode.value = 'current'
      window.location.hash = hashForSection('workspace')
    }
    calendarPanel.value?.refresh()
    historyNotice.value = `聊天记录已删除，同步删除 ${response.deleted_calendar_tasks || 0} 条日历事项。`
    directoryLoaded.value = false
  } catch (e) {
    if (isCurrent(version)) historyError.value = `删除聊天记录失败：${e.message}`
  } finally {
    if (isCurrent(version)) panelBusy.value = false
  }
  if (isCurrent(version) && !historyError.value) await refreshRecords()
}

function changeScope(mode) {
  if (loading.value || panelBusy.value || (mode === 'current' && !shortcutRecordId.value)) return
  scopeMode.value = mode
  if (directoryComponent.value) navigateDirectory(section.value)
}

function openHistoryShortcut({ id, section: next }) {
  navigate(next, id)
}

function syncNavigation() {
  if (loading.value || panelBusy.value) {
    window.history.replaceState(null, '', hashForSection(section.value, directoryRecordId.value))
    return
  }
  const route = routeFromHash(window.location.hash, canViewAdmin.value)
  section.value = route.section
  directoryRecordId.value = route.recordId
  scopeMode.value = route.recordId || route.section === 'workspace' ? 'current' : 'all'
}
window.addEventListener('hashchange', syncNavigation)
onBeforeUnmount(() => window.removeEventListener('hashchange', syncNavigation))

watch(directoryRecordId, () => {
  scopedEpoch += 1
  scopedRecord.value = null
  scopedError.value = ''
  scopedLoading.value = false
}, { flush: 'sync' })

async function loadScopedRecord(force = false) {
  const id = directoryRecordId.value
  if (!id || !currentUser.value || !workspaceReady.value || scopedLoading.value) return
  if (!force && scopedRecord.value?.id === id) return
  const version = sessionVersion.value
  const epoch = ++scopedEpoch
  const active = () => isCurrent(version) && epoch === scopedEpoch && directoryRecordId.value === id
  scopedLoading.value = true
  scopedError.value = ''
  try {
    const cached = !force && directoryCache.get(id)?.record
    const record = cached || await getRecord(id)
    if (!active()) return
    scopedRecord.value = record
    // 切换到另一份聊天时同步工作台；同一份聊天不重置尚未保存的编辑草稿。
    if (recordId.value !== id) showRecord(record)
    directoryCache.set(id, { updatedAt: record.updated_at, record })
  } catch (e) {
    if (active()) {
      scopedRecord.value = null
      scopedError.value = `无法读取这份聊天 #${id}：${e.message}`
    }
  } finally {
    if (active()) scopedLoading.value = false
  }
}

async function loadDirectory() {
  if (!currentUser.value || !workspaceReady.value || recordsLoading.value || directoryLoading.value || directoryLoaded.value) return
  if (historyError.value) {
    directoryError.value = historyError.value
    return
  }
  const version = sessionVersion.value
  const epoch = ++directoryEpoch
  const active = () => isCurrent(version) && epoch === directoryEpoch
  directoryLoading.value = true
  directoryError.value = ''
  directoryProgress.value = 0
  try {
    const loaded = await loadRecordDetails(records.value, getRecord, {
      cache: directoryCache, isCurrent: active,
      onProgress: (count) => { if (active()) directoryProgress.value = count },
    })
    if (!active()) return
    directoryRecords.value = loaded.records
    directoryFailures.value = loaded.failures
    directoryLoaded.value = true
  } catch (e) {
    if (active()) directoryError.value = `分类加载失败：${e.message}`
  } finally {
    if (active()) directoryLoading.value = false
  }
}

async function refreshDirectory() {
  if (directoryRecordId.value) {
    if (!loading.value && !panelBusy.value) await loadScopedRecord(true)
    return
  }
  if (directoryLoading.value || loading.value || panelBusy.value || recordsLoading.value) return
  const version = sessionVersion.value
  directoryCache.clear()
  if (await refreshRecords()) await loadDirectory()
  else if (isCurrent(version)) directoryError.value = historyError.value
}

async function openDirectoryRecord(record) {
  if (loading.value || panelBusy.value) return
  const version = sessionVersion.value
  navigate('workspace')
  // 当前记录保持挂载及编辑草稿；点击同一来源不重新读取以免覆盖未保存内容。
  if (isCurrent(version) && record.id !== recordId.value) await openRecord(record)
}

watch([section, directoryRecordId, workspaceReady, recordsLoading], () => {
  if (!directoryComponent.value || !workspaceReady.value) return
  if (directoryRecordId.value) loadScopedRecord()
  else if (!recordsLoading.value) loadDirectory()
})

function isCurrent(version) {
  return !!currentUser.value && sessionVersion.value === version
}

function rememberRecord(id) {
  if (!currentUser.value) return
  try { localStorage.setItem(`keyoushu.lastRecordId.${currentUser.value.id}`, String(id)) } catch { /* 存储不可用不影响接口。 */ }
}

function showRecord(record) {
  recordId.value = record.id
  result.value = record.result
  originalText.value = record.text || ''
  sourceImage.value = record.source_image || ''
  directoryCache.set(record.id, { updatedAt: record.updated_at, record })
  rememberRecord(record.id)
}

// 事件处理器捕获渲染时的账号版本，避免已卸载面板的迟到事件污染新账号。
const handleSaved = computed(() => {
  const version = sessionVersion.value
  return async (record) => {
    if (!isCurrent(version)) return
    showRecord(record)
    await refreshRecords()
  }
})

const handlePanelBusy = computed(() => {
  const version = sessionVersion.value
  return (value) => { if (isCurrent(version)) panelBusy.value = value }
})

async function handleAnalyze(payload) {
  if (!currentUser.value || loading.value || panelBusy.value) return
  const version = sessionVersion.value
  loading.value = true
  error.value = ''
  sourceImage.value = ''
  try {
    const response = await analyze(payload)
    if (!isCurrent(version)) return
    recordId.value = response.id ?? null
    result.value = response
    originalText.value = payload.text || ''
    sourceImage.value = ''
    if (response.id) {
      rememberRecord(response.id)
      try {
        const record = await getRecord(response.id)
        if (!isCurrent(version)) return
        showRecord(record)
      } catch (e) {
        if (isCurrent(version)) error.value = `分析已完成，但原文读取失败：${e.message}`
      }
    }
    if (isCurrent(version)) await refreshRecords()
  } catch (e) {
    if (isCurrent(version)) error.value = e instanceof Error ? e.message : '分析失败，请稍后重试'
  } finally {
    if (isCurrent(version)) loading.value = false
  }
}

async function refreshRecords() {
  if (!currentUser.value) return false
  const version = sessionVersion.value
  directoryEpoch += 1
  directoryLoading.value = false
  directoryLoaded.value = false
  recordsLoading.value = true
  historyError.value = ''
  try {
    const response = await listRecords()
    if (!isCurrent(version)) return false
    records.value = response
    directoryError.value = ''
    return true
  } catch (e) {
    if (isCurrent(version)) historyError.value = e instanceof Error ? `历史记录加载失败：${e.message}` : '历史记录加载失败，请重试'
    return false
  } finally {
    if (isCurrent(version)) recordsLoading.value = false
  }
}

async function openRecord(record) {
  if (!currentUser.value || loading.value || panelBusy.value) return
  const version = sessionVersion.value
  loading.value = true
  error.value = ''
  try {
    const full = await getRecord(record.id)
    if (isCurrent(version)) showRecord(full)
  } catch (e) {
    if (isCurrent(version)) error.value = e instanceof Error ? `无法打开记录 #${record.id}：${e.message}` : '记录加载失败，请重试'
  } finally {
    if (isCurrent(version)) loading.value = false
  }
}

function resetWorkspace() {
  historyNotice.value = ''
  calendarImportMessage.value = ''
  calendarImportError.value = ''
  scopedEpoch += 1
  scopedRecord.value = null
  scopedLoading.value = false
  scopedError.value = ''
  directoryEpoch += 1
  directoryCache.clear()
  directoryRecords.value = []
  directoryFailures.value = []
  directoryLoaded.value = false
  directoryLoading.value = false
  directoryError.value = ''
  directoryProgress.value = 0
  workspaceReady.value = false
  records.value = []
  result.value = null
  recordId.value = null
  originalText.value = ''
  sourceImage.value = ''
  error.value = ''
  historyError.value = ''
  loading.value = false
  recordsLoading.value = false
  panelBusy.value = false
  section.value = currentUser.value ? sectionFromHash(window.location.hash, canViewAdmin.value) : 'workspace'
  directoryRecordId.value = currentUser.value ? routeFromHash(window.location.hash, canViewAdmin.value).recordId : null
  scopeMode.value = directoryRecordId.value || section.value === 'workspace' ? 'current' : 'all'
}

async function initializeWorkspace() {
  const version = sessionVersion.value
  const userId = currentUser.value?.id
  const refreshed = await refreshRecords()
  if (!isCurrent(version)) return
  let lastId
  try { lastId = Number(localStorage.getItem(`keyoushu.lastRecordId.${userId}`)) } catch { /* 存储不可用时仍加载目录。 */ }
  if (!directoryRecordId.value && Number.isInteger(lastId) && lastId > 0) await openRecord({ id: lastId })
  if (!isCurrent(version)) return
  workspaceReady.value = true
  if (directoryRecordId.value) await loadScopedRecord()
  else if (!refreshed) directoryError.value = historyError.value
  else if (directoryComponent.value) await loadDirectory()
}

watch(sessionVersion, () => {
  resetWorkspace()
  if (currentUser.value) initializeWorkspace()
  else if (!notice.value) notice.value = '请登录后继续使用。'
}, { flush: 'sync' })

function handleAuthenticated(data) {
  restoreFailed.value = false
  notice.value = ''
  establishSession(data)
}

async function restoreLogin() {
  if (authChecking.value) return
  authChecking.value = true
  restoreFailed.value = false
  const token = getAuthToken()
  try {
    if (token) restoreSessionUser(await getCurrentUser(), token)
  } catch (e) {
    if (getAuthToken() === token && e.status !== 401) {
      restoreFailed.value = true
      notice.value = `暂时无法验证登录状态：${e.message}。可重试或重新登录。`
    } else notice.value = '登录已失效，请重新登录。'
  } finally {
    authReady.value = true
    authChecking.value = false
  }
}

async function handleLogout() {
  if (loggingOut.value) return
  const token = getAuthToken()
  loggingOut.value = true
  try {
    await logout()
    notice.value = '已退出，服务端登录凭据已撤销。'
  } catch (e) {
    notice.value = e.status === 401 ? '登录已失效。' : `本机已退出，但未能确认服务端撤销：${e.message}。原凭据可能在到期前仍有效。`
  } finally {
    clearSession(token)
    loggingOut.value = false
  }
}

// 仅在首次展示及真实页面切换时上报，不因刷新统计或数据加载重复计数。
watch(() => authReady.value ? `${currentUser.value?.id || 'anonymous'}:${currentUser.value ? section.value : 'login'}` : '', (page) => {
  if (page && currentUser.value) trackPageView().catch(() => { /* 统计失败不阻塞业务。 */ })
})

restoreLogin()
</script>

<template>
  <p v-if="!authReady" role="status">正在验证登录状态…</p>
  <template v-else-if="!currentUser">
    <LoginPanel :notice="notice" @authenticated="handleAuthenticated" />
    <button v-if="restoreFailed" class="restore-button" type="button" :disabled="authChecking" @click="restoreLogin">{{ authChecking ? '正在重试…' : '重试恢复登录' }}</button>
  </template>
  <div v-else :key="sessionVersion" class="layout">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark"><AppIcon name="leaf" :size="25" /></span><div><strong>客有数<span class="brand-dot">.</span></strong><span class="brand-subtitle">让好生意，自然发生</span></div></div>
      <div class="sidebar-label">工作空间</div>
      <button type="button" class="current-nav" :disabled="loading || panelBusy" :aria-current="section === 'workspace' ? 'page' : undefined" @click="navigate('workspace')"><AppIcon name="workspace" :size="17" /><span>需求工作台</span><span v-if="section === 'workspace'" class="nav-dot"></span></button>
      <button v-if="canViewAdmin" type="button" class="current-nav" :aria-current="section === 'admin' ? 'page' : undefined" :disabled="loading || panelBusy" @click="navigate('admin')"><AppIcon name="shield" :size="17" />网站后台统计</button>
      <RecordList
        v-if="section !== 'admin'"
        :records="records"
        :loading="recordsLoading || loading || panelBusy"
        :error="historyError"
        :notice="historyNotice"
        :selected-id="shortcutRecordId"
        :active-section="directoryRecordId ? section : ''"
        :allow-delete="canWrite"
        @select="openDirectoryRecord"
        @shortcut="openHistoryShortcut"
        @delete="removeHistoryRecord"
        @refresh="refreshRecords"
      />
      <SidebarDirectories :section="section" :counts="directoryCounts" :disabled="loading || panelBusy" :record-id="shortcutRecordId" :record-title="shortcutRecordTitle" :scope="scopeMode" @navigate="navigateDirectory" @scope="changeScope" />
      <div class="sidebar-footer"><AppIcon name="shield" :size="18" /><div>云端分析 · 本机留存<span>聊天资料保存在这台电脑</span></div></div>
    </aside>
    <main class="main">
      <header class="topbar"><span>工作空间 <span class="breadcrumb-divider">/</span> <strong>{{ sectionTitle }}</strong></span><div class="session-tools"><span class="user-name">{{ currentUser.username }}</span><span class="avatar" aria-hidden="true">{{ currentUser.username.slice(0, 1) }}</span><button v-if="canViewAdmin" type="button" :disabled="loading || panelBusy" @click="navigate(section === 'admin' ? 'workspace' : 'admin')">{{ section === 'admin' ? '返回工作台' : '后台统计' }}</button><button type="button" :disabled="loggingOut" @click="handleLogout">{{ loggingOut ? '退出中…' : '退出登录' }}</button></div></header>
      <div v-if="section === 'admin' && canViewAdmin" class="workspace"><AdminPanel /></div>
      <div v-if="isCalendar" class="workspace"><CalendarPanel ref="calendarPanel" :key="sessionVersion" :view="section === 'calendar/gantt' ? 'gantt' : 'calendar'" :disabled="!canWrite" @navigate="navigate" @busy="handlePanelBusy" /></div>
      <div v-if="directoryComponent" class="workspace">
        <p v-if="section === 'tasks' && calendarImportMessage" role="status">{{ calendarImportMessage }}</p>
        <p v-if="section === 'tasks' && calendarImportError" class="error" role="alert">{{ calendarImportError }}</p>
        <component :is="directoryComponent" :items="activeViews[section]" :allow-import="section === 'tasks' && canWrite" @import="addSuggestionToCalendar" :loading="!workspaceReady || (directoryRecordId ? scopedLoading : directoryLoading || recordsLoading)" :error="directoryRecordId ? scopedError : directoryError" :failures="directoryRecordId ? [] : directoryFailures" :progress="directoryRecordId ? (scopedRecord ? 1 : 0) : directoryProgress" :total="directoryRecordId ? 1 : records.length" :scoped-record-id="directoryRecordId" :scope-label="directoryRecordId ? `范围：当前聊天 · ${shortcutRecordTitle} · #${directoryRecordId}` : ''" :disabled="loading || panelBusy" @select="openDirectoryRecord" @refresh="refreshDirectory" />
      </div>
      <div v-show="section === 'workspace'" class="workspace">
      <header class="page-header"><div><div class="eyebrow">A LITTLE CLARITY. A BETTER DAY.</div><h1>今天，也让生意简单一点。</h1><p>从客户聊天中梳理需求，让每一次沟通都有清晰的下一步。</p></div><span class="workspace-label"><AppIcon name="shield" :size="16" />先核对，再使用</span></header>
      <section v-if="!result" class="hero" aria-label="需求工作台介绍">
        <div class="hero-copy"><span class="hero-tag"><i></i>给忙碌的生意，一个得力助手</span><h2>客户随口一说，<br />我们帮你理出<span>下一步。</span></h2><p>不必反复翻聊天，不用从头填表。<br />把沟通交给客有数，把时间留给客户。</p><button class="hero-action" type="button" :disabled="loading || panelBusy" @click="focusChatInput">开始整理<AppIcon name="arrow" :size="17" /></button></div>
        <div class="hero-art" aria-hidden="true"><div class="art-orbit"></div><span class="art-spark">✳</span><div class="art-chat"><span class="art-caption">一段客户聊天 · 示意</span><p>“想做一批团建文化衫，<br />大概100件，时间还没定…”</p><span class="chat-dots">· · ·</span></div><div class="art-brief"><div class="art-brief-title"><span><AppIcon name="file" :size="16" />需求小卡片 · 示意</span><AppIcon name="check" :size="16" /></div><div class="brief-row"><span>产品</span><strong>团建文化衫</strong></div><div class="brief-row"><span>数量</span><strong>约 100 件</strong></div><div class="brief-row"><span>交付时间</span><em>待确认</em></div><div class="brief-foot">从模糊的对话，到清晰的行动</div></div><span class="art-note">让每一句话，都有着落。</span></div>
      </section>
      <div v-if="!result" class="step-grid" aria-label="操作流程"><div class="step-card"><span class="step-symbol"><AppIcon name="message" :size="20" /></span><div><h3>放入客户沟通</h3><p>粘贴文字或上传聊天截图</p></div><span class="step-index">01</span></div><div class="step-card"><span class="step-symbol"><AppIcon name="file" :size="20" /></span><div><h3>核对需求与问题</h3><p>查看原文依据，补齐待确认事项</p></div><span class="step-index">02</span></div><div class="step-card"><span class="step-symbol"><AppIcon name="calendar" :size="20" /></span><div><h3>安排下一步行动</h3><p>把建议待办同步到日程计划</p></div><span class="step-index">03</span></div></div>
      <div class="work-grid"><div ref="inputArea" class="work-main">
      <ChatInput :loading="loading || panelBusy" @submit="handleAnalyze" />
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <ResultPanel
        :session-active="!!currentUser"
        :session-key="sessionVersion"
        :result="result"
        :record-id="recordId"
        :original-text="originalText"
        :source-image="sourceImage"
        :disabled="loading"
        @saved="handleSaved"
        @busy="handlePanelBusy"
      />
      </div><aside class="work-aside" aria-label="跟进建议"><section class="guide-card"><div class="aside-heading"><AppIcon name="leaf" :size="18" />少一点忙乱，多一点笃定</div><h3>好的跟进，<br />从问对问题开始。</h3><p>客户没说清楚的，不用猜。<br />先确认这三件小事：</p><ul><li><span>01</span><div><strong>要多少？</strong><small>数量、规格和使用场景</small></div></li><li><span>02</span><div><strong>预算是多少？</strong><small>单件预算还是总预算</small></div></li><li><span>03</span><div><strong>什么时候需要？</strong><small>具体收货日期和地点</small></div></li></ul><div class="guide-foot"><AppIcon name="shield" :size="15" />没确认的价格、交期，不作承诺</div></section><section class="schedule-card"><span class="pill">让行动有着落</span><AppIcon class="schedule-art" name="calendar" :size="74" /><h3>整理好需求，<br />也安排好下一步。</h3><p>有截止日的任务放进日历，尚未排期的事项留在待办池。</p><button type="button" :disabled="loading || panelBusy" @click="navigate('calendar')">查看日程计划<AppIcon name="arrow" :size="16" /></button></section></aside></div>
      <footer class="workspace-footer"><span>客有数 · 把沟通变成行动</span><span>分析结果可编辑，请核对原文后使用</span></footer>
      </div>
    </main>
  </div>
</template>


<style scoped>
.layout { display:grid; grid-template-columns:260px minmax(0,1fr); min-height:100vh; }
.sidebar { background:#f3f3ec; border-right:1px solid var(--line); padding:28px 18px 20px; display:flex; flex-direction:column; position:sticky; top:0; height:100vh; min-width:0; overflow-y:auto; scrollbar-width:thin; }
.brand { display:flex; align-items:center; gap:11px; padding:0 10px 28px; }
.brand-mark { width:42px; height:44px; background:var(--brand); color:#f3e5af; border-radius:13px 13px 13px 3px; display:grid; place-items:center; }
.brand strong { color:var(--ink); font-size:25px; letter-spacing:1px; }
.brand-dot { color:#84916a; }.brand-subtitle { display:block; font-size:11px; margin-top:4px; color:#7c846f; }
.sidebar-label { font-size:11px; color:#7d856f; margin:0 12px 10px; letter-spacing:1px; }
.current-nav { justify-content:flex-start; flex-shrink:0; width:100%; padding:12px; border:1px solid transparent; background:transparent; color:#6b765f; border-radius:9px; font-size:13px; margin-bottom:8px; }
.current-nav[aria-current=page] { background:#e3e8d9; color:#3d5035; font-weight:650; border-color:#dce3ce; }
.nav-dot { width:6px; height:6px; background:#728356; border-radius:50%; margin-left:auto; }
.sidebar-footer { display:flex; gap:10px; align-items:center; margin-top:auto; padding:22px 9px 0; border-top:1px solid var(--line); font-size:12px; color:#647258; }.sidebar-footer span { display:block; font-size:11px; color:#838d77; margin-top:5px; }
.main { min-width:0; }.topbar { min-height:70px; padding:12px 34px; border-bottom:1px solid var(--line); background:#fdfdf8; display:flex; align-items:center; justify-content:space-between; font-size:12px; color:#7e8773; gap:12px; }.topbar strong { color:#56644b; font-weight:500; }.breadcrumb-divider { margin:0 10px; color:#b9c0ac; }
.session-tools { display:flex; align-items:center; gap:9px; min-width:0; }.session-tools button { padding:6px 10px; font-size:12px; }.user-name { max-width:150px; overflow:hidden; text-overflow:ellipsis; }.avatar { display:grid; place-items:center; width:32px; height:32px; flex-shrink:0; background:#e9ecdd; border:2px solid white; border-radius:50%; color:#61714c; }
.restore-button { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); }
.workspace { max-width:1480px; margin:auto; padding:30px 34px 22px; }.page-header { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:24px; }.page-header h1 { font-size:clamp(23px,2.2vw,30px); font-weight:650; line-height:1.5; margin:8px 0; color:var(--ink); }.page-header p { color:var(--muted); font-size:13px; line-height:1.8; margin-bottom:0; }.workspace-label { display:flex; align-items:center; gap:7px; font-size:12px; color:#748165; white-space:nowrap; }
.hero { min-height:318px; border-radius:18px; background:#e9eddf; display:grid; grid-template-columns:1fr 1fr; padding:30px 36px; overflow:hidden; position:relative; }.hero-copy { position:relative; z-index:1; }.hero-tag { display:inline-flex; align-items:center; gap:7px; padding:6px 10px; border-radius:30px; font-size:11px; background:#f7f9edb0; color:#627450; border:1px solid #ffffff90; }.hero-tag i { width:5px; height:5px; border-radius:50%; background:#7d8e65; }.hero h2 { font-size:clamp(27px,2.65vw,39px); font-weight:650; color:#34432a; line-height:1.5; margin:14px 0 10px; }.hero h2 span { position:relative; white-space:nowrap; z-index:1; }.hero h2 span:after { content:''; position:absolute; height:9px; bottom:3px; left:0; right:0; background:#e9d786; z-index:-1; border-radius:40%; }.hero-copy p { color:#6f7d62; font-size:13px; line-height:1.9; margin-bottom:17px; }.hero-action { background:var(--brand); color:white; border-color:var(--brand); }.hero-action:hover:not(:disabled) { background:#435634; color:white; }
.hero-art { position:relative; min-height:265px; }.art-orbit { width:260px; height:260px; border:1px solid #d5ddc6; border-radius:50%; position:absolute; right:12px; top:14px; box-shadow:0 0 0 32px #dce3cd40,0 0 0 64px #dce3cd20; }.art-spark { position:absolute; top:-7px; right:4%; font-size:52px; color:#9aab7a; transform:rotate(12deg); }.art-chat { position:absolute; top:16px; left:8px; transform:rotate(-5deg); width:240px; border-radius:12px; background:#fcfcf5; padding:16px 19px 6px; box-shadow:0 8px 20px #6f7e5512; border:1px solid white; }.art-caption { font-size:11px; color:#7f8d6c; }.art-chat p { font-size:13px; margin:12px 0 0; color:#576547; line-height:1.8; }.chat-dots { color:#a8ae97; font-size:18px; }.art-brief { position:absolute; width:235px; right:12px; top:116px; background:#fffef7; transform:rotate(4deg); border-radius:11px; padding:15px 17px 0; box-shadow:0 12px 32px #5c69451c; border:1px solid white; }.art-brief-title { display:flex; justify-content:space-between; color:#50613c; font-size:12px; margin-bottom:11px; }.art-brief-title span { display:flex; align-items:center; gap:6px; }.brief-row { display:flex; justify-content:space-between; font-size:12px; margin-bottom:9px; color:#8b937c; }.brief-row strong { color:#5c6a4b; font-weight:500; }.brief-row em { font-style:normal; color:#9b8648; background:#f6efce; padding:2px 6px; border-radius:4px; }.brief-foot { margin:10px -17px 0; padding:10px 12px; background:#f6f7ed; font-size:10px; color:#7e8c69; border-radius:0 0 11px 11px; }.art-note { position:absolute; bottom:-9px; left:10px; font-size:11px; color:#899676; }
.step-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:13px; margin:18px 0 28px; }.step-card { display:flex; align-items:center; gap:11px; padding:17px 14px; background:#fffef8; border:1px solid var(--line); border-radius:11px; min-width:0; }.step-symbol { display:grid; place-items:center; width:36px; height:36px; flex-shrink:0; border-radius:10px; background:#eef2e4; color:#7b8a66; }.step-card h3 { font-size:13px; font-weight:600; color:#58664a; margin:0 0 5px; }.step-card p { font-size:11px; line-height:1.7; color:#838d76; margin:0; }.step-index { font:italic 22px Georgia,serif; margin-left:auto; color:#d7dccb; }
.work-grid { display:grid; grid-template-columns:minmax(0,1fr) 250px; gap:24px; align-items:start; }.work-main { min-width:0; }.work-aside { display:grid; gap:18px; }.guide-card { padding:24px; background:#eff2e5; border:1px solid #e3e8d6; border-radius:14px; }.aside-heading { display:flex; gap:8px; align-items:center; font-size:11px; color:#7c8c64; }.guide-card h3 { font-size:23px; font-weight:500; line-height:1.55; color:#526444; margin:19px 0 12px; }.guide-card p { font-size:12px; line-height:1.9; color:#7e8a6e; }.guide-card ul { list-style:none; padding:0; margin:22px 0; }.guide-card li { display:flex; gap:13px; margin-bottom:19px; }.guide-card li > span { color:#a2af8b; font:italic 22px Georgia,serif; }.guide-card strong { color:#60734c; font-weight:500; font-size:13px; }.guide-card small { display:block; font-size:11px; color:#7e8b6c; margin-top:5px; line-height:1.7; }.guide-foot { display:flex; gap:6px; border-top:1px dashed #d6dec7; padding-top:15px; font-size:11px; line-height:1.8; color:#7e8c68; }
.schedule-card { position:relative; padding:24px; background:#f3e9bb; border-radius:14px; overflow:hidden; }.pill { display:inline-block; background:#faf3d7; color:#8b783e; padding:4px 8px; border-radius:5px; font-size:11px; }.schedule-card h3 { color:#6c653e; font-size:22px; font-weight:500; line-height:1.5; margin:15px 0 10px; position:relative; }.schedule-card p { color:#8a7e53; font-size:12px; line-height:1.9; position:relative; }.schedule-card button { background:#fff9df; border-color:#d5c88e; color:#7d6e3e; position:relative; font-size:12px; }.schedule-art { position:absolute; right:4px; bottom:-10px; color:#e0cf92; transform:rotate(-12deg); pointer-events:none; }
.workspace-footer { display:flex; justify-content:space-between; gap:12px; padding:20px 0 0; margin-top:28px; border-top:1px solid var(--line); color:#8a947a; font-size:11px; line-height:1.8; }
@media(max-width:1200px) { .layout { grid-template-columns:236px minmax(0,1fr); }.workspace { padding:26px 24px 20px; }.topbar { padding:12px 24px; }.work-grid { grid-template-columns:minmax(0,1fr) 225px; gap:18px; }.hero { padding:28px; }.art-chat { width:205px; left:-4px; }.art-brief { width:205px; right:0; }.step-index { display:none; }.step-card { padding:14px 11px; gap:8px; }.guide-card,.schedule-card { padding:20px; } }
@media(max-width:1050px) { .work-grid { grid-template-columns:minmax(0,1fr); }.work-aside { grid-template-columns:1fr 1fr; }.workspace-label { display:none; }.hero h2 { font-size:27px; }.art-chat { width:185px; }.art-brief { width:190px; right:-8px; }.art-note { display:none; }.hero { padding:24px; }.hero-tag { font-size:10px; }.step-card { align-items:flex-start; }.step-symbol { width:29px; height:29px; }.topbar { flex-wrap:wrap; } }
@media(max-width:760px) { .layout { display:block; }.sidebar { position:static; height:auto; max-height:none; padding:20px 16px 16px; border-right:0; border-bottom:1px solid var(--line); }.brand { padding:0 4px 18px; }.brand strong { font-size:23px; }.sidebar-label,.sidebar-footer { display:none; }.current-nav { min-height:38px; margin-bottom:5px; padding:9px 12px; }.topbar { padding:12px 16px; gap:10px; }.session-tools { flex-wrap:wrap; }.session-tools button { min-height:34px; }.workspace { padding:24px 16px 18px; }.page-header h1 { font-size:23px; }.page-header .eyebrow { font-size:10px; }.hero { grid-template-columns:1fr 1fr; }.hero h2 { font-size:28px; }.hero-art { min-height:280px; }.art-chat { width:200px; top:25px; }.art-brief { width:200px; top:130px; right:0; }.step-card { flex-direction:column; }.step-card p { font-size:11px; }.workspace-footer { flex-wrap:wrap; } }
@media(max-width:520px) { .hero { grid-template-columns:minmax(0,1fr); padding:25px; }.hero h2 { font-size:30px; }.hero-art { min-height:255px; margin-top:10px; }.art-chat { top:12px; left:4px; width:195px; }.art-brief { top:112px; right:0; width:190px; }.art-orbit { width:190px; height:190px; right:10px; }.art-spark { font-size:38px; right:0; }.hero-copy p br { display:none; }.work-aside { grid-template-columns:minmax(0,1fr); }.guide-card h3 br,.schedule-card h3 br { display:none; }.step-grid { gap:7px; }.step-card { padding:12px 9px; }.step-card h3 { line-height:1.6; font-size:12px; }.step-card p { font-size:11px; }.user-name { max-width:95px; }.session-tools { gap:7px; }.workspace-footer { flex-direction:column; gap:3px; } }
</style>
