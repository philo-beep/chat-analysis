<!-- 结果与编辑，B 负责 -->
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { actOnRecord, exportRecordData, getRecord, saveRecord, trackCopy } from '../api.js'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  result: { type: Object, default: null },
  recordId: { type: Number, default: null },
  originalText: { type: String, default: '' },
  sourceImage: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  sessionActive: { type: Boolean, default: true },
  sessionKey: { type: [String, Number], default: 'default' },
})
const emit = defineEmits(['saved', 'busy'])
const draft = ref(null)
const savedSnapshot = ref('')
const busy = ref(false)
const message = ref('')
const error = ref('')
const operationVersion = ref(0)
const questionAnswers = ref({})
const locked = computed(() => busy.value || props.disabled)
const dirty = computed(() => draft.value && JSON.stringify(draft.value) !== savedSnapshot.value)
const hasExpandedResult = computed(() => Array.isArray(draft.value?.ddl_tasks) || Array.isArray(draft.value?.suggested_tasks))
const suggestionCount = computed(() => (draft.value?.tasks?.length || 0) + (draft.value?.suggested_tasks?.length || 0))
const priorityLabel = { high: '高', medium: '中', low: '低' }

function legacyTaskState(index) {
  return draft.value?.action_states?.[String(index)] || { status: 'pending' }
}

function statusText(status) {
  return { accepted: '已采纳', ignored: '已忽略', added: '已加入日历', confirmed: '已确认' }[status] || ''
}

function setDraft(value) {
  draft.value = value ? JSON.parse(JSON.stringify(value)) : null
  if (draft.value) delete draft.value.id
  savedSnapshot.value = JSON.stringify(draft.value)
  questionAnswers.value = Object.fromEntries((draft.value?.questions || []).map((item, index) => [index, typeof item === 'object' ? item.confirmed_answer || item.initial_guess || '' : '']))
}

watch(() => [props.result, props.recordId], () => {
  setDraft(props.sessionActive ? props.result : null)
  message.value = ''
  error.value = ''
}, { immediate: true })

function clearSessionState() {
  operationVersion.value += 1
  draft.value = null
  savedSnapshot.value = ''
  questionAnswers.value = {}
  message.value = ''
  error.value = ''
  if (busy.value) setBusy(false)
}

watch(() => [props.sessionActive, props.sessionKey], clearSessionState, { flush: 'sync' })
onBeforeUnmount(clearSessionState)

function setBusy(value) {
  busy.value = value
  emit('busy', value)
}

function validate() {
  if (!props.sessionActive) throw new Error('登录状态已失效，请重新登录后打开记录')
  if (!draft.value) throw new Error('当前没有可操作的分析结果')
  if (!props.recordId) throw new Error('当前结果缺少记录编号，请重新打开历史记录')
  if (draft.value.requirements.some((item) => !item.field.trim() || !item.value.trim() || !item.evidence.trim())) {
    throw new Error('请补全每条需求的字段、值和原文依据，或删除空白需求')
  }
}

function isCurrent(version, recordId) {
  return props.sessionActive && operationVersion.value === version && props.recordId === recordId
}

async function persist(version, recordId) {
  validate()
  await saveRecord(recordId, draft.value)
  if (!isCurrent(version, recordId)) return false
  // 从服务端重读，确保成功提示对应已持久化的数据。
  const record = await getRecord(recordId)
  if (!isCurrent(version, recordId)) return false
  setDraft(record.result)
  emit('saved', record)
  return true
}

async function save() {
  if (locked.value) return
  error.value = ''
  message.value = ''
  const version = ++operationVersion.value
  const id = props.recordId
  setBusy(true)
  try {
    if (await persist(version, id) && isCurrent(version, id)) {
      message.value = '已保存，刷新或重新打开历史记录可查看'
    }
  } catch (e) {
    if (isCurrent(version, id)) error.value = e instanceof Error ? e.message : '保存失败，请重试'
  } finally {
    if (isCurrent(version, id)) setBusy(false)
  }
}

async function performAction(action, index, source = null, answer = null) {
  if (locked.value) return
  const values = action === 'confirm_question' ? draft.value.questions : action === 'add_ddl_task' ? draft.value.ddl_tasks : draft.value[source]
  const item = values?.[index]
  const title = typeof item === 'string' ? item : item?.title || item?.question
  if (!title?.trim()) { error.value = '请先填写完整内容'; return }
  if (action === 'confirm_question' && !answer?.trim()) { error.value = '请填写确认答案'; return }
  const version = ++operationVersion.value
  const id = props.recordId
  error.value = ''; message.value = ''
  setBusy(true)
  try {
    validate()
    if (dirty.value && !(await persist(version, id))) return
    const expected = JSON.parse(JSON.stringify(draft.value))
    delete expected.id
    const payload = { action, index, expected_result: expected }
    if (source) payload.kind = source
    if (answer !== null) payload.answer = answer.trim()
    await actOnRecord(id, payload)
    if (!isCurrent(version, id)) return
    const record = await getRecord(id)
    if (!isCurrent(version, id)) return
    if (!record.result) throw new Error('操作已提交，请重新打开这份聊天核对结果')
    setDraft(record.result)
    emit('saved', record)
    message.value = action === 'add_ddl_task' ? '已加入日历，可在日程计划查看' : action === 'accept_suggestion' ? '已加入待办池，可在日程计划安排时间' : action === 'ignore_suggestion' ? '已忽略这条建议' : '答案已确认并保存'
  } catch (e) {
    if (isCurrent(version, id)) error.value = e instanceof Error ? e.message : '操作失败，请重试'
  } finally {
    if (isCurrent(version, id)) setBusy(false)
  }
}

async function copyReply() {
  if (locked.value || !props.sessionActive || !draft.value) return
  error.value = ''
  message.value = ''
  const version = operationVersion.value
  const id = props.recordId
  try {
    if (!navigator.clipboard?.writeText) throw new Error('浏览器不支持剪贴板，请手动选择并复制回复草稿')
    await navigator.clipboard.writeText(draft.value.reply)
    if (props.sessionActive && operationVersion.value === version) {
      message.value = '回复草稿已复制'
      if (id && isCurrent(version, id)) trackCopy(id).catch(() => { /* 统计失败不影响复制。 */ })
    }
  } catch (e) {
    if (props.sessionActive && operationVersion.value === version) {
      error.value = e instanceof Error ? `复制失败：${e.message}` : '复制失败，请手动复制回复草稿'
    }
  }
}

async function exportJson() {
  if (locked.value) return
  error.value = ''
  message.value = ''
  const version = ++operationVersion.value
  const id = props.recordId
  setBusy(true)
  try {
    validate()
    // 导出前先保存，再经统一导出请求校验权限并记录真实导出调用。
    if (dirty.value && !(await persist(version, id))) return
    const record = await exportRecordData(id)
    if (!isCurrent(version, id)) return
    if (!record || !record.result) {
      throw new Error('服务端返回的记录不完整，无法导出')
    }
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `record-${id}.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    if (isCurrent(version, id)) message.value = '已生成完整需求单，包含原文、结果和记录信息'
  } catch (e) {
    if (isCurrent(version, id)) error.value = e instanceof Error ? e.message : '导出失败，请检查后端连接后重试'
  } finally {
    if (isCurrent(version, id)) setBusy(false)
  }
}
</script>

<template>
  <section v-if="draft && sessionActive" class="result-panel card" aria-label="分析结果编辑面板">
    <header class="result-heading"><div class="section-title"><span class="section-icon"><AppIcon name="file" /></span><div><div class="eyebrow">CUSTOMER BRIEF</div><h2>分析结果 <small v-if="recordId">#{{ recordId }}</small></h2></div></div><span class="result-status" :class="{ pending: dirty }"><span></span>{{ dirty ? '有待保存修改' : '已保存至本地' }}</span></header>
    <div class="result-content">
    <p v-if="draft.is_sample === true" class="sample-flag" role="status">
      演示结果：以下为经过校验的预置样例，本次未调用云端分析。日期及事项请核对原文；修改输入后将进行真实分析。
    </p>
    <p v-else-if="draft.is_sample !== false" class="hint">旧记录未标注分析来源，请核对原文。</p>
    <div class="result-overview"><div><span>已梳理需求</span><strong>{{ draft.requirements.length }}<small>项</small></strong></div><div><span>待确认问题</span><strong>{{ draft.questions.length }}<small>项</small></strong></div><div><span>建议待办</span><strong>{{ suggestionCount }}<small>项</small></strong></div></div>
    <details :key="`${sessionKey}:${recordId}`" class="original">
      <summary>原始聊天记录（用于核对依据）<span class="original-toggle"><span class="when-closed">展开原文</span><span class="when-open">收起原文</span></span></summary>
      <div class="original-content" tabindex="0" aria-label="原始聊天记录，可滚动查看完整内容">
      <figure v-if="sourceImage" class="source-image">
        <img :src="sourceImage" alt="此记录上传的原始聊天截图，可与下方识别文字核对" />
        <figcaption>原始聊天截图</figcaption>
      </figure>
      <pre>{{ originalText || '暂无可核对的文字原文；截图解析完成后可在此查看识别文本。' }}</pre>
      </div>
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
      <div v-for="(question, index) in draft.questions" :key="index" :class="typeof question === 'string' ? 'list-row' : 'analysis-item'">
        <template v-if="typeof question === 'string'">
          <input v-model="draft.questions[index]" :aria-label="`待确认问题 ${index + 1}`" />
          <button type="button" class="ghost" @click="draft.questions.splice(index, 1)">删除问题</button>
        </template>
        <template v-else>
          <label :for="`question-${recordId}-${index}`">{{ question.question }}</label>
          <p v-if="question.status !== 'confirmed'" class="hint">初步判断：{{ question.initial_guess }}</p>
          <p v-else class="confirmed-answer">已确认：{{ question.confirmed_answer }}</p>
          <label class="hint" :for="`question-${recordId}-${index}`">{{ question.status === 'confirmed' ? '修改答案' : '请确认或修改答案' }}</label>
          <input :id="`question-${recordId}-${index}`" v-model="questionAnswers[index]" :aria-label="`问题 ${index + 1} 的答案`" />
          <div class="item-actions"><button type="button" class="ghost" @click="performAction('confirm_question', index, null, questionAnswers[index])">{{ question.status === 'confirmed' ? '修改确认' : '确认答案' }}</button></div>
        </template>
      </div>
      <p v-if="!draft.questions.length" class="hint">暂无待确认问题</p>
      <button type="button" class="ghost" @click="draft.questions.push('')">添加问题</button>
      </section><section class="followup-block">
      <h3><span class="section-number">03</span>建议待办</h3>
      <p class="hint">供商家安排下一步，不代表已经向客户作出承诺。</p>
      <div v-for="(_, index) in draft.tasks" :key="`ordinary-${index}`" class="analysis-item">
        <span v-if="hasExpandedResult" class="item-kind">普通建议</span>
        <div class="list-row">
        <input v-model="draft.tasks[index]" :aria-label="`建议待办 ${index + 1}`" />
        <button type="button" class="ghost" @click="draft.tasks.splice(index, 1)">删除待办</button>
        </div>
        <div class="item-actions">
          <span v-if="statusText(legacyTaskState(index).status)" class="hint">{{ statusText(legacyTaskState(index).status) }}</span>
          <button type="button" class="ghost" :disabled="legacyTaskState(index).status === 'accepted'" @click="performAction('accept_suggestion', index, 'tasks')">采纳</button>
          <button type="button" class="ghost" :disabled="legacyTaskState(index).status === 'ignored' || legacyTaskState(index).status === 'accepted'" @click="performAction('ignore_suggestion', index, 'tasks')">忽略</button>
        </div>
      </div>
      <div v-for="(item, index) in draft.suggested_tasks || []" :key="`suggested-${index}`" class="analysis-item">
        <div class="suggestion-title"><strong>{{ item.title }}</strong><span class="priority" :class="item.priority">{{ priorityLabel[item.priority] || item.priority }}优先</span></div>
        <p class="hint">建议理由：{{ item.reason }}</p>
        <div class="item-actions">
          <span v-if="statusText(item.status)" class="hint">{{ statusText(item.status) }}</span>
          <button type="button" class="ghost" :disabled="item.status === 'accepted'" @click="performAction('accept_suggestion', index, 'suggested_tasks')">采纳</button>
          <button type="button" class="ghost" :disabled="item.status === 'ignored' || item.status === 'accepted'" @click="performAction('ignore_suggestion', index, 'suggested_tasks')">忽略</button>
        </div>
      </div>
      <p v-if="!suggestionCount" class="hint">暂无建议待办</p>
      <button type="button" class="ghost" @click="draft.tasks.push('')">添加待办</button>
      </section></div>
      <h3><span class="section-number">04</span><label for="reply-draft">回复草稿</label></h3>
      <textarea id="reply-draft" v-model="draft.reply" rows="4" />

      <section v-if="Array.isArray(draft.ddl_tasks)" class="ddl-section" aria-label="有截止日期的任务">
        <h3><span class="section-number">05</span>有 DDL 的任务</h3>
        <p class="hint">核对时间和原话后加入日历，助手会按剩余时间显示紧迫程度。</p>
        <div v-for="(item, index) in draft.ddl_tasks" :key="index" class="analysis-item">
          <strong>{{ item.title }}</strong>
          <label class="deadline">截止日期 <input type="date" v-model="item.ddl_date" :aria-label="`任务 ${index + 1} 截止日期`" :disabled="item.status === 'added'" /></label><span v-if="item.date_basis === 'inferred'" class="inferred">推算日期，待确认</span>
          <p v-if="item.start_date" class="hint">开始日期：{{ item.start_date }}</p>
          <blockquote>{{ item.source_quote }}</blockquote>
          <div class="item-actions"><span v-if="item.status === 'added'" class="hint">已加入日历</span><button type="button" class="ghost" :disabled="item.status === 'added'" @click="performAction('add_ddl_task', index)">加入日历</button></div>
        </div>
        <p v-if="!draft.ddl_tasks.length" class="hint">这份聊天里暂时没有约定明确时间的任务</p>
      </section>
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
h2 small { color: var(--muted); font-size: 12px; margin-left: 5px; font-weight: 400; }
.result-heading .eyebrow { font-size: 8px; letter-spacing: 1.3px; }
.result-status { display: flex; align-items: center; gap: 6px; color: #586b45; font-size: 11px; white-space: nowrap; }
.result-status > span { width: 5px; height: 5px; border-radius: 50%; background: #71845f; }
.result-status.pending { color: #8a6a2e; } .result-status.pending > span { background: #b8954b; }
.result-content { padding: 23px 26px 25px; }
.result-overview { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--line); background: #fafbf6; border-radius: 10px; padding: 18px 0; margin-bottom: 22px; }
.result-overview > div { padding: 0 22px; border-right: 1px solid var(--line); }
.result-overview > div:last-child { border: 0; }
.result-overview span { display: block; color: #69765e; font-size: 11px; }
.result-overview strong { display: block; margin-top: 6px; color: #4f6042; font-size: 25px; font-weight: 600; }
.result-overview small { font-size: 10px; color: #6f7c64; font-weight: 400; margin-left: 6px; }
h3 { display: flex; align-items: center; gap: 9px; color: #46533d; font-size: 13px; font-weight: 600; margin: 25px 0 14px; }
.section-number { font-size: 10px; color: var(--brand); background: var(--soft); padding: 3px 5px; border-radius: 4px; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.sample-flag { padding: 12px; border: 2px solid #f59e0b; background: #fffbeb; color: #92400e; border-radius: 6px; font-weight: 600; }
.original { background: #fafbf6; border: 1px solid var(--line); border-radius: 8px; padding: 13px 16px; font-size: 12px; color: #66735c; }
summary { cursor: pointer; color: #526246; font-size: 12px; }
.original-toggle { float: right; margin-left: 12px; color: var(--brand); }
.original .when-open, .original[open] .when-closed { display: none; }
.original[open] .when-open { display: inline; }
.original-content { max-height: min(60vh, 480px); overflow: auto; margin-top: 12px; scrollbar-gutter: stable; }
.original-content:focus-visible { outline: 2px solid var(--brand); outline-offset: 3px; }
.source-image { margin: 12px 0; }
.source-image img { display: block; max-width: 100%; max-height: 480px; width: auto; height: auto; object-fit: contain; }
.source-image figcaption { margin-top: 6px; color: #66735c; font-size: 14px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.6; }
.table-wrap { overflow-x: auto; max-width: 100%; border: 1px solid var(--line); border-radius: 8px; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { border-bottom: 1px solid var(--line); padding: 11px; text-align: left; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
th { background: #f7f8f1; color: #69765e; font-size: 11px; font-weight: 500; }
th:first-child { width: 16%; }
th:nth-child(2) { width: 24%; }
th:last-child { width: 85px; }
td input, td textarea { font-size: 12px; padding: 7px 8px; border-color: transparent; background: #f7f9f2; border-radius: 5px; }
td textarea { min-height: 57px; }
.row-action button { padding: 6px 0; min-height: 30px; border: 0; color: #72806a; font-size: 11px; white-space: nowrap; }
.row-action button:hover { color: #b35555; }
.followup-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; margin-top: 24px; }
.followup-block { background: #fbfcf8; padding: 17px; border: 1px solid var(--line); border-radius: 10px; min-width: 0; }
.followup-block h3 { margin-top: 0; }
.followup-block input { font-size: 12px; padding: 8px 10px; }
.followup-block .ghost { font-size: 11px; padding: 5px 8px; min-height: 30px; }
.list-row { display: flex; align-items: start; gap: 6px; margin-bottom: 8px; }
.list-row button { flex-shrink: 0; }
.analysis-item { padding: 12px; margin-bottom: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); overflow-wrap: anywhere; }
.analysis-item > label:first-child, .analysis-item strong { display: block; font-size: 12px; line-height: 1.8; }
.analysis-item .hint { font-size: 11px; line-height: 1.8; margin: 6px 0; }
.item-kind { display: inline-block; color: var(--muted); font-size: 10px; margin-bottom: 6px; }
.item-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.suggestion-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.priority { border-radius: 5px; padding: 3px 6px; font-size: 10px; white-space: nowrap; background: #eef2e7; color: #536647; }
.priority.high { background: #fce9e5; color: #a63f32; }
.priority.medium { background: #fff3d8; color: #8a641e; }
.priority.low { background: #edf2e8; color: #536647; }
.deadline { font-size: 12px; color: var(--ink); margin: 8px 0; }
.inferred { display: inline-block; color: #8a641e; background: #fff3d8; border-radius: 4px; padding: 2px 5px; font-size: 10px; }
.confirmed-answer { color: #48633d; font-size: 12px; }
blockquote { border-left: 3px solid var(--line); padding: 4px 10px; margin: 8px 0; color: var(--muted); font-size: 12px; line-height: 1.8; }
.actions { margin-top: 22px; padding-top: 21px; border-top: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 9px; }
.success, .error { margin: 15px 0 0; }
.unsaved { color: #82692e; font-size: 12px; margin: 16px 0 0; }
.empty { margin-top: 22px; padding: 32px 24px 28px; text-align: center; border-style: dashed; background: #fffefa; }
.empty-icon { display: grid; place-items: center; width: 54px; height: 54px; margin: 0 auto 14px; background: var(--soft); color: #6d805a; border-radius: 16px; }
.empty h2 { font-size: 14px; font-weight: 500; color: #526246; margin: 0 0 7px; }
.empty p { font-size: 11px; color: #6f7c64; margin-bottom: 20px; }
.empty-steps { display: flex; justify-content: center; gap: 28px; color: #69765e; font-size: 10px; }
.empty-steps span { display: flex; align-items: center; gap: 6px; }
.empty-steps i { font-size: 9px; font-style: normal; color: #758369; }
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
  td[data-label]::before { content: attr(data-label); display: block; font-size: 10px; color: #69765e; margin-bottom: 5px; }
  .row-action { text-align: right; }
  .followup-block { padding: 14px; }
  .actions > button:first-child { flex-basis: 100%; }
}

/* Keep the imported visual direction readable for real, long records. */
.result-panel { border-radius: 12px; background: var(--surface); }
.result-heading { background: var(--surface); }
.result-overview { background: var(--canvas); border-radius: 12px; }
.original, .followup-block { border-radius: 12px; }
.original summary { line-height: 1.7; }
.original-content { color: var(--ink); }
.sample-flag { border-width: 1px; border-color: #d8be65; background: #fcf5d8; border-radius: 10px; }
.section-number { color: var(--brand); font-weight: 600; }
.list-row input { min-width: 0; flex: 1; }
.row-action button { color: #647458; }
.empty-steps, .empty p { font-size: 12px; }
@media (max-width: 420px) {
  .result-content, .result-heading { padding: 15px; }
  .result-overview > div { padding: 0 8px; }
  .result-overview span { line-height: 1.6; }
  .original-toggle { float: none; display: block; margin: 4px 0 0; }
  .list-row { flex-wrap: wrap; }
  .list-row input { flex-basis: 100%; }
}
</style>
