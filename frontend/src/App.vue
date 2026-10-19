<!-- 页面总入口，A 负责 -->
<script setup>
import { computed, ref, watch } from 'vue'
import ChatInput from './components/ChatInput.vue'
import RecordList from './components/RecordList.vue'
import ResultPanel from './components/ResultPanel.vue'
import AppIcon from './components/AppIcon.vue'
import LoginPanel from './components/LoginPanel.vue'
import AdminPanel from './components/AdminPanel.vue'
import { analyze, getRecord, listRecords, getCurrentUser, logout, trackPageView } from './api.js'
import { currentUser, sessionVersion, getAuthToken, establishSession, restoreSessionUser, clearSession } from './auth.js'

const records = ref([])
const result = ref(null)
const loading = ref(false)
const error = ref('')
const historyError = ref('')
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
const section = ref('workspace')
const canViewAdmin = computed(() => currentUser.value?.permissions?.includes('admin:stats'))

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
  if (!currentUser.value) return
  const version = sessionVersion.value
  recordsLoading.value = true
  historyError.value = ''
  try {
    const response = await listRecords()
    if (isCurrent(version)) records.value = response
  } catch (e) {
    if (isCurrent(version)) historyError.value = e instanceof Error ? `历史记录加载失败：${e.message}` : '历史记录加载失败，请重试'
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
  section.value = 'workspace'
}

async function initializeWorkspace() {
  const version = sessionVersion.value
  const userId = currentUser.value?.id
  await refreshRecords()
  if (!isCurrent(version)) return
  let lastId
  try { lastId = Number(localStorage.getItem(`keyoushu.lastRecordId.${userId}`)) } catch { return }
  if (Number.isInteger(lastId) && lastId > 0) await openRecord({ id: lastId })
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
      <div class="brand"><span class="brand-mark"><AppIcon name="workspace" :size="23" /></span><div><strong>客有数<span class="brand-dot">.</span></strong><span class="brand-subtitle">客户需求与跟进助手</span></div></div>
      <div class="sidebar-label">工作空间</div>
      <button type="button" class="current-nav" @click="section = 'workspace'"><AppIcon name="workspace" :size="17" /><span>需求工作台</span><span class="nav-dot"></span></button>
      <button v-if="canViewAdmin" type="button" class="current-nav" @click="section = 'admin'">网站后台统计</button>
      <RecordList
        v-if="section === 'workspace'"
        :records="records"
        :loading="recordsLoading || loading || panelBusy"
        :error="historyError"
        :selected-id="recordId"
        @select="openRecord"
        @refresh="refreshRecords"
      />
      <div class="sidebar-footer"><AppIcon name="shield" :size="18" /><div>本地分析 · 安心留存<span>聊天资料保存在这台电脑</span></div></div>
    </aside>
    <main class="main">
      <header class="topbar"><span>工作空间 <span class="breadcrumb-divider">/</span> <strong>{{ section === 'admin' ? '网站后台统计' : '需求工作台' }}</strong></span><div class="session-tools"><span>{{ currentUser.username }}</span><button v-if="canViewAdmin" type="button" @click="section = section === 'admin' ? 'workspace' : 'admin'">{{ section === 'admin' ? '返回工作台' : '后台统计' }}</button><button type="button" :disabled="loggingOut" @click="handleLogout">{{ loggingOut ? '退出中…' : '退出登录' }}</button></div></header>
      <div v-if="section === 'admin' && canViewAdmin" class="workspace"><AdminPanel /></div>
      <div v-else class="workspace">
      <header class="page-header"><div><div class="eyebrow">CUSTOMER WORKSPACE</div><h1>让每一次沟通，都有清晰的下一步。</h1><p>从客户聊天中梳理需求、识别待确认事项，轻松推进订单跟进。</p></div><span class="workspace-label"><AppIcon name="shield" :size="16" />本机处理</span></header>
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
      <footer class="workspace-footer"><span>客有数 · 把沟通变成行动</span><span>分析结果可编辑，请核对原文后使用</span></footer>
      </div>
    </main>
  </div>
</template>

<style scoped>
.session-tools { display: flex; align-items: center; gap: 10px; }
.session-tools button { padding: 6px 10px; font-size: 12px; }
.restore-button { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); }
.layout {
  display: grid;
  grid-template-columns: 252px minmax(0, 1fr);
  min-height: 100vh;
}
.sidebar {
  background: #14223b;
  color: #c7d1e2;
  padding: 30px 18px 20px;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  min-width: 0;
}
.main {
  min-width: 0;
}
.brand { display: flex; align-items: center; gap: 11px; padding: 0 10px 34px; }
.brand-mark { width: 43px; height: 43px; background: #3159cb; color: white; border-radius: 12px; display: grid; place-items: center; }
.brand strong { color: white; font-size: 24px; letter-spacing: 1px; }
.brand-dot { color: #83a8ff; }
.brand-subtitle { display: block; font-size: 10px; letter-spacing: 1.4px; margin-top: 3px; color: #8c9cb6; }
.sidebar-label { font-size: 11px; color: #7386a5; margin: 0 12px 12px; letter-spacing: 1px; }
.current-nav { display: flex; align-items: center; gap: 10px; padding: 13px 14px; border: 1px solid #4d6da83b; background: #28436a70; color: #e7eeff; border-radius: 8px; font-size: 13px; margin-bottom: 30px; }
.nav-dot { width: 5px; height: 5px; background: #86a9ff; border-radius: 50%; margin-left: auto; }
.sidebar-footer { display: flex; gap: 10px; align-items: center; margin-top: auto; padding: 20px 9px 0; border-top: 1px solid #ffffff12; font-size: 12px; color: #adbad0; }
.sidebar-footer span { display: block; font-size: 10px; color: #7185a4; margin-top: 5px; }
.topbar { height: 66px; padding: 0 38px; border-bottom: 1px solid var(--line); background: #ffffffc9; display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: #8994a7; gap: 10px; }
.topbar strong { color: #48566e; font-weight: 500; }
.breadcrumb-divider { margin: 0 13px; color: #c7cfdd; }
.local-badge { display: flex; align-items: center; gap: 7px; font-size: 11px; white-space: nowrap; }
.local-badge i { width: 6px; height: 6px; background: #62a68d; border-radius: 50%; }
.workspace { max-width: 1240px; margin: auto; padding: 34px 38px 20px; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 26px; }
.page-header h1 { font-size: clamp(21px, 2vw, 27px); letter-spacing: -.5px; color: var(--ink); line-height: 1.5; margin: 9px 0 8px; font-weight: 650; }
.page-header p { font-size: 13px; line-height: 1.8; color: var(--muted); margin-bottom: 0; }
.workspace-label { display: flex; align-items: center; gap: 7px; color: #65758f; font-size: 11px; flex-shrink: 0; }
.workspace-footer { display: flex; justify-content: space-between; gap: 12px; padding: 22px 3px 0; color: #97a2b3; font-size: 10px; line-height: 1.8; }
@media (max-width: 1100px) { .layout { grid-template-columns: 218px minmax(0, 1fr); } .workspace { padding: 28px 24px 18px; } .topbar { padding: 0 24px; } .workspace-label { display: none; } }
@media (max-width: 760px) { .layout { display: block; } .sidebar { position: static; height: auto; padding: 19px 20px; } .brand { padding: 0; } .brand-mark { width: 36px; height: 36px; border-radius: 9px; } .brand strong { font-size: 21px; } .brand-subtitle { font-size: 9px; } .sidebar-label, .current-nav, .sidebar-footer { display: none; } .topbar { height: 50px; padding: 0 20px; } .workspace { padding: 25px 16px 16px; } .page-header { margin-bottom: 22px; } .page-header h1 { font-size: 22px; max-width: 290px; } .workspace-footer { flex-direction: column; gap: 2px; } }
</style>
