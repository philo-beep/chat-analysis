<!-- 页面总入口，A 负责 -->
<script setup>
import { ref } from 'vue'
import ChatInput from './components/ChatInput.vue'
import RecordList from './components/RecordList.vue'
import ResultPanel from './components/ResultPanel.vue'
import { analyze, getRecord, listRecords, saveRecord } from './api.js'

const records = ref([])
const result = ref(null)
const loading = ref(false)
const error = ref('')
const saving = ref(false)
const saveMessage = ref('')

async function handleAnalyze(text) {
  loading.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    result.value = { ...(await analyze(text)), original_text: text }
    records.value = await listRecords()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function refreshRecords() {
  try {
    records.value = await listRecords()
  } catch (e) {
    error.value = e.message
  }
}

// 列表里只有标题和时间，没有 result，所以点开时要按 id 再取一次完整记录。
async function openRecord(record) {
  loading.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    const full = await getRecord(record.id)
    result.value = { ...full.result, id: full.id, original_text: full.text, updated_at: full.updated_at }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function handleSave(updatedResult) {
  if (!updatedResult?.id) {
    error.value = '这条结果还没有记录编号，无法保存。'
    return
  }
  saving.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    const { id, original_text: _originalText, updated_at: _updatedAt, ...data } = updatedResult
    await saveRecord(id, data)
    result.value = { ...updatedResult, ...data }
    await refreshRecords()
    saveMessage.value = '修改已保存'
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

refreshRecords()
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <RecordList :records="records" @select="openRecord" @refresh="refreshRecords" />
    </aside>
    <main class="main">
      <h1>聊天分析</h1>
      <ChatInput :loading="loading" @submit="handleAnalyze" />
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="result && result.is_sample" class="sample-flag">
        当前显示的是开发样例，不是真实模型结果
      </p>
      <ResultPanel
        :result="result"
        :saving="saving"
        :save-message="saveMessage"
        @save="handleSave"
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
