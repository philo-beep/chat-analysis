<!-- 结果与编辑，B 负责 -->
<script setup>
import { computed, ref, watch } from 'vue'
import { exportRecord, getRecord, saveRecord } from '../api.js'

const props = defineProps({
  result: { type: Object, default: null },
  recordId: { type: Number, default: null },
  originalText: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'busy'])
const draft = ref(null)
const savedSnapshot = ref('')
const busy = ref(false)
const message = ref('')
const error = ref('')
const locked = computed(() => busy.value || props.disabled)
const dirty = computed(() => draft.value && JSON.stringify(draft.value) !== savedSnapshot.value)

function setDraft(value) {
  draft.value = value ? JSON.parse(JSON.stringify(value)) : null
  savedSnapshot.value = JSON.stringify(draft.value)
}

watch(() => [props.result, props.recordId], () => {
  setDraft(props.result)
  message.value = ''
  error.value = ''
}, { immediate: true })

function setBusy(value) {
  busy.value = value
  emit('busy', value)
}

function validate() {
  if (!props.recordId) throw new Error('当前结果缺少记录编号，请重新打开历史记录')
  if (draft.value.requirements.some((item) => !item.field.trim() || !item.value.trim() || !item.evidence.trim())) {
    throw new Error('请补全每条需求的字段、值和原文依据，或删除空白需求')
  }
}

async function persist() {
  validate()
  await saveRecord(props.recordId, draft.value)
  // 从服务端重读，确保成功提示对应已持久化的数据。
  const record = await getRecord(props.recordId)
  setDraft(record.result)
  emit('saved', record)
}

async function save() {
  if (locked.value) return
  error.value = ''
  message.value = ''
  setBusy(true)
  try {
    await persist()
    message.value = '已保存，刷新或重新打开历史记录可查看'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败，请重试'
  } finally {
    setBusy(false)
  }
}

async function copyReply() {
  error.value = ''
  message.value = ''
  try {
    if (!navigator.clipboard?.writeText) throw new Error('浏览器不支持剪贴板，请手动选择并复制回复草稿')
    await navigator.clipboard.writeText(draft.value.reply)
    message.value = '回复草稿已复制'
  } catch (e) {
    error.value = e instanceof Error ? `复制失败：${e.message}` : '复制失败，请手动复制回复草稿'
  }
}

async function exportJson() {
  if (locked.value) return
  error.value = ''
  message.value = ''
  setBusy(true)
  try {
    validate()
    // 导出后端完整记录；先保存修改，避免下载到旧结果。
    if (dirty.value) await persist()
    const response = await fetch(exportRecord(props.recordId))
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(typeof body?.detail === 'string' ? body.detail : `导出失败：${response.status}`)
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `record-${props.recordId}.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    message.value = '已生成完整需求单，包含原文、结果和记录信息'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '导出失败，请检查后端连接后重试'
  } finally {
    setBusy(false)
  }
}
</script>

<template>
  <section v-if="draft" class="result-panel" aria-label="分析结果编辑面板">
    <h2>分析结果 <small v-if="recordId">#{{ recordId }}</small></h2>
    <p v-if="draft.is_sample === true" class="sample-flag" role="status">
      开发样例：以下为示例数据，不是真实模型分析，请核对原文后使用。
    </p>
    <p v-else-if="draft.is_sample !== false" class="hint">旧记录未标注分析来源，请核对原文。</p>
    <details open class="original">
      <summary>原始聊天记录（用于核对依据）</summary>
      <pre>{{ originalText || '暂无可核对的文字原文；截图解析完成后可在此查看识别文本。' }}</pre>
    </details>

    <fieldset :disabled="locked">
      <legend class="sr-only">编辑分析结果</legend>
      <h3>客户需求与原文依据</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>字段</th><th>值</th><th>对应原文 evidence</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(item, index) in draft.requirements" :key="index">
              <td><input v-model="item.field" :aria-label="`需求 ${index + 1} 字段`" /></td>
              <td><input v-model="item.value" :aria-label="`需求 ${index + 1} 值`" /></td>
              <td><textarea v-model="item.evidence" rows="2" :aria-label="`需求 ${index + 1} 原文依据`" /></td>
              <td><button type="button" class="ghost" @click="draft.requirements.splice(index, 1)">删除需求</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!draft.requirements.length" class="hint">没有已提取的需求，请核对原文并补充。</p>
      <button type="button" class="ghost" @click="draft.requirements.push({ field: '', value: '', evidence: '' })">添加需求</button>

      <h3>待确认问题</h3>
      <p class="hint">这些信息需要向客户询问，尚未确认。</p>
      <div v-for="(_, index) in draft.questions" :key="index" class="list-row">
        <input v-model="draft.questions[index]" :aria-label="`待确认问题 ${index + 1}`" />
        <button type="button" class="ghost" @click="draft.questions.splice(index, 1)">删除问题</button>
      </div>
      <p v-if="!draft.questions.length" class="hint">暂无待确认问题</p>
      <button type="button" class="ghost" @click="draft.questions.push('')">添加问题</button>

      <h3>建议待办</h3>
      <p class="hint">供商家安排下一步，不代表已经向客户作出承诺。</p>
      <div v-for="(_, index) in draft.tasks" :key="index" class="list-row">
        <input v-model="draft.tasks[index]" :aria-label="`建议待办 ${index + 1}`" />
        <button type="button" class="ghost" @click="draft.tasks.splice(index, 1)">删除待办</button>
      </div>
      <p v-if="!draft.tasks.length" class="hint">暂无建议待办</p>
      <button type="button" class="ghost" @click="draft.tasks.push('')">添加待办</button>

      <h3><label for="reply-draft">回复草稿</label></h3>
      <textarea id="reply-draft" v-model="draft.reply" rows="4" />
    </fieldset>

    <p v-if="dirty" class="unsaved" role="status">有未保存修改。导出时将先保存；切换记录前请先保存。</p>
    <div class="actions">
      <button type="button" :disabled="locked || !recordId" @click="save">{{ busy ? '处理中…' : '保存修改' }}</button>
      <button type="button" :disabled="locked" @click="copyReply">复制回复</button>
      <button type="button" :disabled="locked || !recordId" @click="exportJson">导出需求单 JSON</button>
    </div>
    <p v-if="message" class="success" role="status">{{ message }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </section>
  <p v-else class="empty">分析结果会显示在这里</p>
</template>

<style scoped>
.result-panel { margin-top: 24px; }
h2 small { color: #64748b; font-size: 14px; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.sample-flag { padding: 12px; border: 2px solid #f59e0b; background: #fffbeb; color: #92400e; border-radius: 6px; font-weight: 600; }
.original { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; }
summary { cursor: pointer; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.6; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 560px; }
th, td { border: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }
th:first-child { width: 15%; }
th:nth-child(2) { width: 22%; }
input, textarea { width: 100%; box-sizing: border-box; font: inherit; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: white; }
textarea { resize: vertical; }
button { padding: 8px 12px; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .6; }
.list-row { display: flex; align-items: start; gap: 8px; margin-bottom: 8px; }
.list-row button { flex-shrink: 0; }
.actions { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.hint, .empty { color: #64748b; font-size: 14px; }
.success { color: #166534; }
.error { color: #b91c1c; }
.unsaved { color: #92400e; }
</style>
