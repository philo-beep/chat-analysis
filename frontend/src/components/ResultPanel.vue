<!-- 结果与编辑，B 负责 -->
<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  result: { type: Object, default: null },
})

const draft = ref(null)
const copied = ref(false)

watch(
  () => props.result,
  (value) => {
    draft.value = value ? JSON.parse(JSON.stringify(value)) : null
    copied.value = false
  },
  { immediate: true },
)

function removeRequirement(index) {
  draft.value.requirements.splice(index, 1)
}

function copyReply() {
  navigator.clipboard.writeText(draft.value.reply)
  copied.value = true
}

function exportJson() {
  const blob = new Blob([JSON.stringify(draft.value, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '分析结果.json'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <section v-if="draft" class="result-panel">
    <h2>分析结果</h2>

    <h3>需求</h3>
    <table>
      <thead>
        <tr>
          <th>字段</th>
          <th>值</th>
          <th>依据</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, index) in draft.requirements" :key="index">
          <td><input v-model="item.field" /></td>
          <td><input v-model="item.value" /></td>
          <td><input v-model="item.evidence" /></td>
          <td><button class="ghost" @click="removeRequirement(index)">删除</button></td>
        </tr>
      </tbody>
    </table>

    <h3>待确认问题</h3>
    <ul>
      <li v-for="(q, index) in draft.questions" :key="index">
        <input v-model="draft.questions[index]" />
      </li>
    </ul>

    <h3>建议待办</h3>
    <ul>
      <li v-for="(t, index) in draft.tasks" :key="index">
        <input v-model="draft.tasks[index]" />
      </li>
    </ul>

    <h3>回复草稿</h3>
    <textarea v-model="draft.reply" rows="4" />

    <div class="actions">
      <button @click="copyReply">{{ copied ? '已复制' : '复制回复' }}</button>
      <button @click="exportJson">导出 JSON</button>
    </div>
  </section>

  <p v-else class="empty">分析结果会显示在这里</p>
</template>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  border: 1px solid #e5e7eb;
  padding: 4px;
  text-align: left;
}
input,
textarea {
  width: 100%;
  box-sizing: border-box;
  font: inherit;
  border: none;
  background: transparent;
}
.actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.empty {
  color: #6b7280;
}
</style>
