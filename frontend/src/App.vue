<!-- 页面总入口，A 负责 -->
<script setup>
import { ref } from 'vue'
import ChatInput from './components/ChatInput.vue'
import RecordList from './components/RecordList.vue'
import ResultPanel from './components/ResultPanel.vue'
import AppIcon from './components/AppIcon.vue'
import { analyze, getRecord, listRecords } from './api.js'

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
const lastRecordKey = 'keyoushu.lastRecordId'

function rememberRecord(id) {
  try { localStorage.setItem(lastRecordKey, String(id)) } catch { /* 隐私模式不影响保存接口 */ }
}

function showRecord(record) {
  recordId.value = record.id
  result.value = record.result
  originalText.value = record.text || ''
  sourceImage.value = record.source_image || ''
  rememberRecord(record.id)
}

async function handleSaved(record) {
  showRecord(record)
  await refreshRecords()
}

async function handleAnalyze(payload) {
  if (loading.value || panelBusy.value) return
  loading.value = true
  error.value = ''
  sourceImage.value = ''
  try {
    const response = await analyze(payload)
    recordId.value = response.id ?? null
    result.value = response
    originalText.value = payload.text || ''
    sourceImage.value = ''
    if (response.id) {
      rememberRecord(response.id)
      // 截图的识别原文保存在详情中，分析响应只包含约定业务字段。
      try {
        showRecord(await getRecord(response.id))
      } catch (e) {
        error.value = `分析已完成，但原文读取失败：${e.message}`
      }
    }
    await refreshRecords()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '分析失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function refreshRecords() {
  recordsLoading.value = true
  historyError.value = ''
  try {
    records.value = await listRecords()
  } catch (e) {
    historyError.value = e instanceof Error ? `历史记录加载失败：${e.message}` : '历史记录加载失败，请重试'
  } finally {
    recordsLoading.value = false
  }
}

// 列表里只有标题和时间，没有 result，所以点开时要按 id 再取一次完整记录。
async function openRecord(record) {
  if (loading.value || panelBusy.value) return
  loading.value = true
  error.value = ''
  try {
    const full = await getRecord(record.id)
    showRecord(full)
  } catch (e) {
    error.value = e instanceof Error ? `无法打开记录 #${record.id}：${e.message}` : '记录加载失败，请重试'
  } finally {
    loading.value = false
  }
}

async function initialize() {
  await refreshRecords()
  let lastId
  try { lastId = Number(localStorage.getItem(lastRecordKey)) } catch { return }
  if (Number.isInteger(lastId) && lastId > 0) await openRecord({ id: lastId })
}

initialize()
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark"><AppIcon name="workspace" :size="23" /></span><div><strong>客有数<span class="brand-dot">.</span></strong><span class="brand-subtitle">客户需求与跟进助手</span></div></div>
      <div class="sidebar-label">工作空间</div>
      <div class="current-nav"><AppIcon name="workspace" :size="17" /><span>需求工作台</span><span class="nav-dot"></span></div>
      <RecordList
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
      <header class="topbar"><span>工作空间 <span class="breadcrumb-divider">/</span> <strong>需求工作台</strong></span><span class="local-badge"><i></i>本地工作空间</span></header>
      <div class="workspace">
      <header class="page-header"><div><div class="eyebrow">CUSTOMER WORKSPACE</div><h1>让每一次沟通，都有清晰的下一步。</h1><p>从客户聊天中梳理需求、识别待确认事项，轻松推进订单跟进。</p></div><span class="workspace-label"><AppIcon name="shield" :size="16" />本机处理</span></header>
      <ChatInput :loading="loading || panelBusy" @submit="handleAnalyze" />
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <ResultPanel
        :result="result"
        :record-id="recordId"
        :original-text="originalText"
        :source-image="sourceImage"
        :disabled="loading"
        @saved="handleSaved"
        @busy="panelBusy = $event"
      />
      <footer class="workspace-footer"><span>客有数 · 把沟通变成行动</span><span>分析结果可编辑，请核对原文后使用</span></footer>
      </div>
    </main>
  </div>
</template>

<style scoped>
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
