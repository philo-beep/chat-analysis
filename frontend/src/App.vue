<!-- 页面总入口，A 负责 -->
<script setup>
import { ref } from 'vue'
import ChatInput from './components/ChatInput.vue'
import RecordList from './components/RecordList.vue'
import ResultPanel from './components/ResultPanel.vue'
import { analyze, listRecords } from './api.js'

const records = ref([])
const result = ref(null)
const loading = ref(false)
const error = ref('')

async function handleAnalyze(text) {
  loading.value = true
  error.value = ''
  try {
    result.value = await analyze(text)
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

refreshRecords()
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <RecordList :records="records" @select="(r) => (result = r.result)" @refresh="refreshRecords" />
    </aside>
    <main class="main">
      <h1>聊天分析</h1>
      <ChatInput :loading="loading" @submit="handleAnalyze" />
      <p v-if="error" class="error">{{ error }}</p>
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
</style>
