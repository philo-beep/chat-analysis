<!-- 页面总入口，A 负责 -->
<script setup>
import { ref } from 'vue'
import ChatInput from './components/ChatInput.vue'
import RecordList from './components/RecordList.vue'
import ResultPanel from './components/ResultPanel.vue'
import { analyze, getRecord, listRecords } from './api.js'

const records = ref([])
const result = ref(null)
const loading = ref(false)
const error = ref('')
const recordId = ref(null)
const recordsLoading = ref(false)
const originalText = ref('')
const panelBusy = ref(false)
const lastRecordKey = 'keyoushu.lastRecordId'

function rememberRecord(id) {
  try { localStorage.setItem(lastRecordKey, String(id)) } catch { /* 隐私模式不影响保存接口 */ }
}

function showRecord(record) {
  recordId.value = record.id
  result.value = record.result
  originalText.value = record.text || ''
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
  try {
    const response = await analyze(payload)
    recordId.value = response.id ?? null
    result.value = response
    originalText.value = payload.text || ''
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
  try {
    records.value = await listRecords()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '历史记录加载失败'
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
    error.value = e instanceof Error ? e.message : '记录加载失败'
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
      <RecordList
        :records="records"
        :loading="recordsLoading || loading || panelBusy"
        :error="error"
        @select="openRecord"
        @refresh="refreshRecords"
      />
    </aside>
    <main class="main">
      <h1>客有数 · 客户需求整理</h1>
      <ChatInput :loading="loading || panelBusy" @submit="handleAnalyze" />
      <p v-if="error" class="error">{{ error }}</p>
      <ResultPanel
        :result="result"
        :record-id="recordId"
        :original-text="originalText"
        :disabled="loading"
        @saved="handleSaved"
        @busy="panelBusy = $event"
      />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 240px;
  border-right: 1px solid #e5e7eb;
  padding: 16px;
}
.main {
  flex: 1;
  padding: 24px;
  max-width: 900px;
}
.error {
  color: #dc2626;
}
.sample-flag {
  padding: 8px 12px;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 4px;
  font-size: 14px;
}
</style>
