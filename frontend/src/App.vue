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

async function handleAnalyze(payload) {
  loading.value = true
  error.value = ''
  try {
    const response = await analyze(payload)
    recordId.value = response.id ?? null
    result.value = response
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
  loading.value = true
  error.value = ''
  try {
    const full = await getRecord(record.id)
    recordId.value = full.id
    result.value = full.result
  } catch (e) {
    error.value = e instanceof Error ? e.message : '记录加载失败'
  } finally {
    loading.value = false
  }
}

refreshRecords()
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <RecordList
        :records="records"
        :loading="recordsLoading"
        :error="error"
        @select="openRecord"
        @refresh="refreshRecords"
      />
    </aside>
    <main class="main">
      <h1>聊天分析</h1>
      <ChatInput :loading="loading" @submit="handleAnalyze" />
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="result && result.is_sample" class="sample-flag">
        当前显示的是开发样例，不是真实模型结果
      </p>
      <ResultPanel :result="result" />
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
