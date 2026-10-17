<!-- 结果与编辑，B 负责 -->
<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  result: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  saveMessage: { type: String, default: '' },
})
const emit = defineEmits(['save'])
const draft = ref(null)
const copied = ref(false)
const copyError = ref('')

function cloneResult(value) {
  if (!value) return null
  return {
    ...JSON.parse(JSON.stringify(value)),
    requirements: Array.isArray(value.requirements) ? JSON.parse(JSON.stringify(value.requirements)) : [],
    questions: Array.isArray(value.questions) ? [...value.questions] : [],
    tasks: Array.isArray(value.tasks) ? [...value.tasks] : [],
    reply: typeof value.reply === 'string' ? value.reply : '',
  }
}

watch(() => props.result, (value) => {
  draft.value = cloneResult(value)
  copied.value = false
  copyError.value = ''
}, { immediate: true, deep: true })

const originalText = computed(() => draft.value?.original_text || '')

function removeRequirement(index) { draft.value.requirements.splice(index, 1) }
function addRequirement() { draft.value.requirements.push({ field: '', value: '', evidence: '' }) }
function removeItem(type, index) { draft.value[type].splice(index, 1) }
function addItem(type) { draft.value[type].push('') }

async function copyReply() {
  copyError.value = ''
  try {
    await navigator.clipboard.writeText(draft.value.reply || '')
    copied.value = true
  } catch (_error) {
    copyError.value = '复制失败，请手动选择并复制回复内容。'
  }
}

function save() { emit('save', cloneResult(draft.value)) }

function exportJson() {
  const exportData = { ...draft.value, text: draft.value.original_text || '' }
  delete exportData.original_text
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `需求记录-${draft.value.id || '未保存'}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <section v-if="draft" class="result-panel">
    <div class="panel-heading">
      <div><p class="eyebrow">客户需求整理</p><h2>分析结果</h2></div>
      <span class="record-id" v-if="draft.id">记录 #{{ draft.id }}</span>
    </div>

    <div v-if="originalText" class="source-block">
      <div class="section-heading"><div><p class="eyebrow">核对来源</p><h3>原始聊天记录</h3></div></div>
      <p class="source-text">{{ originalText }}</p>
    </div>

    <div class="section-heading">
      <div><p class="eyebrow">已提取信息</p><h3>需求清单</h3></div>
      <button class="secondary small" type="button" @click="addRequirement">新增需求</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>字段</th><th>值</th><th>对应原文</th><th aria-label="操作"></th></tr></thead>
        <tbody>
          <tr v-for="(item, index) in draft.requirements" :key="index">
            <td><input v-model="item.field" placeholder="如：数量" /></td>
            <td><input v-model="item.value" placeholder="待确认" /></td>
            <td><textarea v-model="item.evidence" rows="2" placeholder="粘贴对应原文" /></td>
            <td><button class="icon-button danger" type="button" title="删除需求" @click="removeRequirement(index)">删除</button></td>
          </tr>
          <tr v-if="!draft.requirements.length"><td class="empty-cell" colspan="4">暂无需求信息，可点击“新增需求”补充。</td></tr>
        </tbody>
      </table>
    </div>

    <div class="two-columns">
      <div class="list-section">
        <div class="section-heading compact"><div><p class="eyebrow">避免遗漏</p><h3>待确认问题</h3></div><button class="text-button" type="button" @click="addItem('questions')">+ 添加</button></div>
        <div v-if="draft.questions.length" class="editable-list">
          <div v-for="(question, index) in draft.questions" :key="index" class="editable-item">
            <input v-model="draft.questions[index]" placeholder="输入待确认问题" />
            <button class="icon-button danger" type="button" title="删除问题" @click="removeItem('questions', index)">删除</button>
          </div>
        </div>
        <p v-else class="muted">暂无待确认问题</p>
      </div>
      <div class="list-section">
        <div class="section-heading compact"><div><p class="eyebrow">下一步行动</p><h3>建议待办</h3></div><button class="text-button" type="button" @click="addItem('tasks')">+ 添加</button></div>
        <div v-if="draft.tasks.length" class="editable-list">
          <div v-for="(task, index) in draft.tasks" :key="index" class="editable-item">
            <input v-model="draft.tasks[index]" placeholder="输入建议待办" />
            <button class="icon-button danger" type="button" title="删除待办" @click="removeItem('tasks', index)">删除</button>
          </div>
        </div>
        <p v-else class="muted">暂无建议待办</p>
      </div>
    </div>

    <div class="reply-section">
      <div class="section-heading"><div><p class="eyebrow">可继续修改</p><h3>回复草稿</h3></div><button class="secondary small" type="button" @click="copyReply">{{ copied ? '已复制' : '复制回复' }}</button></div>
      <textarea v-model="draft.reply" class="reply-editor" rows="5" placeholder="输入给客户的回复草稿" />
      <p v-if="copyError" class="inline-error">{{ copyError }}</p>
    </div>

    <div class="actions">
      <span v-if="saveMessage" class="save-message">{{ saveMessage }}</span>
      <button class="primary" type="button" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存修改' }}</button>
      <button class="secondary" type="button" @click="exportJson">导出需求单</button>
    </div>
  </section>

  <section v-else class="empty-state"><div class="empty-icon">＋</div><h2>分析结果会显示在这里</h2><p>先粘贴一段客户聊天记录，分析后即可整理、编辑并保存需求。</p></section>
</template>

<style scoped>
.result-panel, .empty-state { background: #fff; border: 1px solid #e6e9ef; border-radius: 8px; box-shadow: 0 12px 30px rgba(24, 39, 75, .06); }
.result-panel { padding: 28px; }
.panel-heading, .section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.panel-heading { margin-bottom: 26px; }
.eyebrow { margin: 0 0 5px; color: #6b7280; font-size: 11px; font-weight: 700; letter-spacing: 0; text-transform: uppercase; }
h2, h3 { margin: 0; color: #172033; } h2 { font-size: 22px; } h3 { font-size: 16px; }
.record-id { color: #56647a; font-size: 13px; white-space: nowrap; }
.source-block { margin-bottom: 26px; padding: 16px; border: 1px solid #e4e8ef; border-radius: 8px; background: #f8fafc; }
.source-text { margin: 12px 0 0; color: #3f4b5f; font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
.section-heading { margin-bottom: 12px; } .section-heading.compact { align-items: center; margin-bottom: 10px; }
.table-wrap { overflow-x: auto; margin-bottom: 26px; border: 1px solid #e4e8ef; border-radius: 8px; }
table { width: 100%; min-width: 680px; border-collapse: collapse; }
th { color: #68758a; background: #f8fafc; font-size: 12px; font-weight: 700; text-align: left; }
th, td { padding: 11px 12px; border-bottom: 1px solid #edf0f4; vertical-align: top; } tr:last-child td { border-bottom: 0; }
input, textarea { width: 100%; box-sizing: border-box; border: 1px solid transparent; border-radius: 5px; background: transparent; color: #1f2937; font: inherit; line-height: 1.5; }
input { min-height: 34px; padding: 6px 8px; } textarea { min-height: 48px; padding: 6px 8px; resize: vertical; }
input:hover, input:focus, textarea:hover, textarea:focus { border-color: #cbd5e1; background: #fff; outline: none; }
.empty-cell { padding: 24px; color: #7b8798; text-align: center; }
.two-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px; margin-bottom: 26px; }
.editable-list { display: grid; gap: 8px; } .editable-item { display: flex; align-items: center; gap: 8px; padding: 4px; border: 1px solid #e4e8ef; border-radius: 6px; }
.editable-item input { min-width: 0; } .muted { margin: 0; color: #8792a2; font-size: 13px; }
.reply-section { padding-top: 20px; border-top: 1px solid #edf0f4; } .reply-editor { display: block; min-height: 122px; padding: 12px; border-color: #dce2ea; background: #fbfcfe; }
.actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; margin-top: 20px; padding-top: 18px; border-top: 1px solid #edf0f4; }
.save-message { margin-right: auto; color: #18794e; font-size: 13px; font-weight: 600; }
button { border: 0; border-radius: 6px; font: inherit; font-weight: 600; cursor: pointer; } button:disabled { cursor: not-allowed; opacity: .6; }
.primary, .secondary { min-height: 38px; padding: 0 16px; } .primary { color: #fff; background: #1f6feb; } .primary:hover:not(:disabled) { background: #185abc; }
.secondary { color: #344155; background: #eef2f7; } .secondary:hover { background: #e2e8f0; } .secondary.small { min-height: 30px; padding: 0 10px; font-size: 12px; }
.text-button { padding: 2px 0; color: #1f6feb; background: transparent; font-size: 12px; } .icon-button { flex: 0 0 auto; padding: 5px 6px; color: #6b7280; background: transparent; font-size: 12px; }
.icon-button.danger:hover { color: #b42318; background: #fff1f0; } .inline-error { margin: 8px 0 0; color: #b42318; font-size: 12px; }
.empty-state { padding: 70px 24px; color: #728096; text-align: center; } .empty-state h2 { margin-top: 12px; font-size: 18px; } .empty-state p { margin: 8px auto 0; max-width: 360px; line-height: 1.6; }
.empty-icon { display: inline-grid; width: 42px; height: 42px; place-items: center; border-radius: 50%; color: #1f6feb; background: #eaf2ff; font-size: 24px; }
@media (max-width: 720px) { .result-panel { padding: 18px; } .two-columns { grid-template-columns: 1fr; } .actions { justify-content: stretch; } .actions button { flex: 1; } }
</style>
