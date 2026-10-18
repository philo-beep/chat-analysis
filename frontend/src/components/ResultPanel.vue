<!-- 结果与编辑，B 负责 -->
<script setup>
import { computed, ref, watch } from 'vue'
import { exportRecord, getRecord, saveRecord } from '../api.js'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  result: { type: Object, default: null },
  recordId: { type: Number, default: null },
  originalText: { type: String, default: '' },
  sourceImage: { type: String, default: '' },
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
  <section v-if="draft" class="result-panel card" aria-label="分析结果编辑面板">
    <header class="result-heading"><div class="section-title"><span class="section-icon"><AppIcon name="file" /></span><div><div class="eyebrow">CUSTOMER BRIEF</div><h2>分析结果 <small v-if="recordId">#{{ recordId }}</small></h2></div></div><span class="result-status" :class="{ pending: dirty }"><span></span>{{ dirty ? '有待保存修改' : '已保存至本地' }}</span></header>
    <div class="result-content">
    <p v-if="draft.is_sample === true" class="sample-flag" role="status">
      开发样例：以下为示例数据，不是真实模型分析，请核对原文后使用。
    </p>
    <p v-else-if="draft.is_sample !== false" class="hint">旧记录未标注分析来源，请核对原文。</p>
    <div class="result-overview"><div><span>已梳理需求</span><strong>{{ draft.requirements.length }}<small>项</small></strong></div><div><span>待确认问题</span><strong>{{ draft.questions.length }}<small>项</small></strong></div><div><span>建议待办</span><strong>{{ draft.tasks.length }}<small>项</small></strong></div></div>
    <details open class="original">
      <summary>原始聊天记录（用于核对依据）</summary>
      <figure v-if="sourceImage" class="source-image">
        <img :src="sourceImage" alt="此记录上传的原始聊天截图，可与下方识别文字核对" />
        <figcaption>原始聊天截图</figcaption>
      </figure>
      <pre>{{ originalText || '暂无可核对的文字原文；截图解析完成后可在此查看识别文本。' }}</pre>
    </details>

    <fieldset :disabled="locked">
      <legend class="sr-only">编辑分析结果</legend>
      <h3><span class="section-number">01</span>客户需求与原文依据</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>需求类型</th><th>需求内容</th><th>对应原文</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(item, index) in draft.requirements" :key="index">
              <td data-label="需求类型"><input v-model="item.field" :aria-label="`需求 ${index + 1} 字段`" /></td>
              <td data-label="需求内容"><input v-model="item.value" :aria-label="`需求 ${index + 1} 值`" /></td>
              <td data-label="对应原文"><textarea v-model="item.evidence" rows="2" :aria-label="`需求 ${index + 1} 原文依据`" /></td>
              <td class="row-action"><button type="button" class="ghost" @click="draft.requirements.splice(index, 1)">删除需求</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!draft.requirements.length" class="hint">没有已提取的需求，请核对原文并补充。</p>
      <button type="button" class="ghost" @click="draft.requirements.push({ field: '', value: '', evidence: '' })">添加需求</button>

      <div class="followup-grid"><section class="followup-block">
      <h3><span class="section-number">02</span>待确认问题</h3>
      <p class="hint">这些信息需要向客户询问，尚未确认。</p>
      <div v-for="(_, index) in draft.questions" :key="index" class="list-row">
        <input v-model="draft.questions[index]" :aria-label="`待确认问题 ${index + 1}`" />
        <button type="button" class="ghost" @click="draft.questions.splice(index, 1)">删除问题</button>
      </div>
      <p v-if="!draft.questions.length" class="hint">暂无待确认问题</p>
      <button type="button" class="ghost" @click="draft.questions.push('')">添加问题</button>
      </section><section class="followup-block">
      <h3><span class="section-number">03</span>建议待办</h3>
      <p class="hint">供商家安排下一步，不代表已经向客户作出承诺。</p>
      <div v-for="(_, index) in draft.tasks" :key="index" class="list-row">
        <input v-model="draft.tasks[index]" :aria-label="`建议待办 ${index + 1}`" />
        <button type="button" class="ghost" @click="draft.tasks.splice(index, 1)">删除待办</button>
      </div>
      <p v-if="!draft.tasks.length" class="hint">暂无建议待办</p>
      <button type="button" class="ghost" @click="draft.tasks.push('')">添加待办</button>
      </section></div>
      <h3><span class="section-number">04</span><label for="reply-draft">回复草稿</label></h3>
      <textarea id="reply-draft" v-model="draft.reply" rows="4" />
    </fieldset>

    <p v-if="dirty" class="unsaved" role="status">有未保存修改。导出时将先保存；切换记录前请先保存。</p>
    <div class="actions">
      <button type="button" class="primary" :disabled="locked || !recordId" @click="save"><AppIcon name="check" :size="16" />{{ busy ? '处理中…' : '保存修改' }}</button>
      <button type="button" :disabled="locked" @click="copyReply">复制回复</button>
      <button type="button" :disabled="locked || !recordId" @click="exportJson">导出需求单 JSON</button>
    </div>
    <p v-if="message" class="success" role="status">{{ message }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    </div>
  </section>
  <section v-else class="empty card"><span class="empty-icon"><AppIcon name="file" :size="28" /></span><h2>把客户沟通，整理成清晰的需求单</h2><p>分析结果会显示在这里</p><div class="empty-steps"><span><i>01</i>提取需求与原文</span><span><i>02</i>明确待确认事项</span><span><i>03</i>生成跟进建议</span></div></section>
</template>

<style scoped>
.result-panel { margin-top: 24px; overflow: hidden; min-width: 0; }
.result-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 22px 26px; border-bottom: 1px solid var(--line); }
h2 { font-size: 16px; font-weight: 600; margin: 5px 0 0; color: var(--ink); }
h2 small { color: #95a1b4; font-size: 12px; margin-left: 5px; font-weight: 400; }
.result-heading .eyebrow { font-size: 8px; letter-spacing: 1.3px; }
.result-status { display: flex; align-items: center; gap: 6px; color: #6e8c80; font-size: 11px; white-space: nowrap; }
.result-status > span { width: 5px; height: 5px; border-radius: 50%; background: #6b9c89; }
.result-status.pending { color: #b68d4a; } .result-status.pending > span { background: #c7a366; }
.result-content { padding: 23px 26px 25px; }
.result-overview { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--line); background: #fafbfd; border-radius: 10px; padding: 18px 0; margin-bottom: 22px; }
.result-overview > div { padding: 0 22px; border-right: 1px solid var(--line); }
.result-overview > div:last-child { border: 0; }
.result-overview span { display: block; color: #8390a5; font-size: 11px; }
.result-overview strong { display: block; margin-top: 6px; color: #344a73; font-size: 25px; font-weight: 600; }
.result-overview small { font-size: 10px; color: #9aa4b4; font-weight: 400; margin-left: 6px; }
h3 { display: flex; align-items: center; gap: 9px; color: #3d4d67; font-size: 13px; font-weight: 600; margin: 25px 0 14px; }
.section-number { font-size: 10px; color: #7190cb; background: #eef3fd; padding: 3px 5px; border-radius: 4px; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.sample-flag { padding: 12px; border: 2px solid #f59e0b; background: #fffbeb; color: #92400e; border-radius: 6px; font-weight: 600; }
.original { background: #fafbfd; border: 1px solid var(--line); border-radius: 8px; padding: 13px 16px; font-size: 12px; color: #7d8aa0; }
summary { cursor: pointer; color: #61738f; font-size: 12px; }
.source-image { margin: 12px 0; }
.source-image img { display: block; max-width: 100%; max-height: 480px; width: auto; height: auto; object-fit: contain; }
.source-image figcaption { margin-top: 6px; color: #64748b; font-size: 14px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.6; }
.table-wrap { overflow-x: auto; max-width: 100%; border: 1px solid var(--line); border-radius: 8px; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { border-bottom: 1px solid var(--line); padding: 11px; text-align: left; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
th { background: #f7f9fc; color: #8996aa; font-size: 11px; font-weight: 500; }
th:first-child { width: 16%; }
th:nth-child(2) { width: 24%; }
th:last-child { width: 85px; }
td input, td textarea { font-size: 12px; padding: 7px 8px; border-color: transparent; background: #f8fafd; border-radius: 5px; }
td textarea { min-height: 57px; }
.row-action button { padding: 6px 0; min-height: 30px; border: 0; color: #a2aabb; font-size: 11px; white-space: nowrap; }
.row-action button:hover { color: #b35555; }
.followup-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; margin-top: 24px; }
.followup-block { background: #fbfcfe; padding: 17px; border: 1px solid var(--line); border-radius: 10px; min-width: 0; }
.followup-block h3 { margin-top: 0; }
.followup-block input { font-size: 12px; padding: 8px 10px; }
.followup-block .ghost { font-size: 11px; padding: 5px 8px; min-height: 30px; }
.list-row { display: flex; align-items: start; gap: 6px; margin-bottom: 8px; }
.list-row button { flex-shrink: 0; }
.actions { margin-top: 22px; padding-top: 21px; border-top: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 9px; }
.success, .error { margin: 15px 0 0; }
.unsaved { color: #aa884d; font-size: 12px; margin: 16px 0 0; }
.empty { margin-top: 22px; padding: 32px 24px 28px; text-align: center; border-style: dashed; background: #ffffff85; }
.empty-icon { display: grid; place-items: center; width: 54px; height: 54px; margin: 0 auto 14px; background: #edf1f9; color: #8ba0c3; border-radius: 16px; }
.empty h2 { font-size: 14px; font-weight: 500; color: #5f7190; margin: 0 0 7px; }
.empty p { font-size: 11px; color: #a0aaba; margin-bottom: 20px; }
.empty-steps { display: flex; justify-content: center; gap: 28px; color: #8c9bb1; font-size: 10px; }
.empty-steps span { display: flex; align-items: center; gap: 6px; }
.empty-steps i { font-size: 9px; font-style: normal; color: #a6b3c9; }
@media (max-width: 1100px) { .followup-grid { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) {
  .result-content, .result-heading { padding: 18px; }
  .result-heading { flex-wrap: wrap; }
  .result-status { font-size: 10px; }
  .result-overview > div { padding: 0 10px; }
  .result-overview span { font-size: 10px; }
  .result-overview strong { font-size: 22px; }
  .empty { padding: 26px 15px; }
  .empty h2 { font-size: 13px; }
  .empty-steps { gap: 12px; flex-wrap: wrap; }
  .table-wrap { border: 0; border-radius: 0; }
  table, tbody, tr, td { display: block; width: 100%; }
  thead { display: none; }
  tr { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-bottom: 10px; }
  td { border: 0; padding: 5px 0; }
  td[data-label]::before { content: attr(data-label); display: block; font-size: 10px; color: #8a98ad; margin-bottom: 5px; }
  .row-action { text-align: right; }
  .followup-block { padding: 14px; }
  .actions > button:first-child { flex-basis: 100%; }
}
</style>
