<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  title: String, description: String, emptyText: String,
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  failures: { type: Array, default: () => [] },
  progress: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  disabled: { type: Boolean, default: false },
  scopedRecordId: { type: Number, default: null },
  scopeLabel: { type: String, default: '' },
  allowImport: { type: Boolean, default: false },
})
defineEmits(['select', 'refresh', 'import'])
</script>

<template>
  <section class="record-content card" :aria-label="title">
    <header>
      <div><h1>{{ title }} <span>{{ items.length }}</span></h1><p class="hint">{{ description }}</p><p class="hint scope">{{ scopeLabel || `范围：最近 100 条可访问的分析记录 · 当前列表 ${total} 条` }}</p><button v-if="scopedRecordId" class="ghost" :disabled="loading || disabled" @click="$emit('select', { id: scopedRecordId })">打开这份聊天</button></div>
      <button class="ghost" :disabled="loading || disabled" @click="$emit('refresh')"><AppIcon name="refresh" :size="14" />刷新</button>
    </header>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="loading" class="empty" role="status">正在加载{{ title }}… {{ progress }} / {{ total }}</p>
    <template v-else>
      <div v-if="failures.length" class="error" role="alert">
        有 {{ failures.length }} 条来源记录读取失败，当前结果可能不完整，请刷新重试。
        <ul><li v-for="failure in failures" :key="failure.id">记录 #{{ failure.id }}：{{ failure.message }}</li></ul>
      </div>
      <div v-if="!items.length && !failures.length" class="empty"><AppIcon name="file" :size="27" /><p>{{ emptyText }}</p><span>可返回需求工作台分析聊天，保存后在这里查看。</span></div>
      <ul v-else class="items">
        <li v-for="item in items" :key="item.key">
          <button class="item" :disabled="disabled" @click="$emit('select', { id: item.recordId })">
            <img v-if="item.image" :src="item.image" alt="原始聊天截图缩略图" loading="lazy" />
            <span class="item-body"><span class="text">{{ item.text }}</span><span v-if="item.reason" class="source">建议理由：{{ item.reason }}</span><span v-if="item.dueDate" class="source">截止日期：{{ item.dueDate }}</span><span v-if="item.initialGuess || item.confirmedAnswer" class="source">{{ item.confirmedAnswer ? `已确认：${item.confirmedAnswer}` : `初步判断：${item.initialGuess}` }}</span><span v-if="item.isSample" class="sample">开发样例</span><span class="source">来源：{{ item.title }} · #{{ item.recordId }}</span><span class="time"><AppIcon name="clock" :size="11" />{{ item.createdAt }} · 打开来源记录</span></span>
          </button>
          <button v-if="allowImport" class="import-task ghost" :disabled="disabled || loading || item.status === 'added' || item.status === 'accepted'" @click="$emit('import', item)">{{ item.status === 'added' || item.status === 'accepted' ? '已加入日程计划' : item.kind === 'ddl_tasks' ? '加入日历' : '加入待办池' }}</button>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.record-content { padding: 24px; }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 18px; }
h1 { font-size: 22px; margin-bottom: 10px; color: var(--ink); }
h1 span { font-size: 12px; margin-left: 8px; background: var(--soft); color: var(--brand); padding: 3px 8px; border-radius: 4px; }
.hint { margin-bottom: 6px; }
.scope { font-size: 11px; }
.items { list-style: none; padding: 0; margin: 0; }
.import-task { margin: 0 0 14px 12px; font-size: 12px; }
.item { width: 100%; justify-content: flex-start; align-items: flex-start; text-align: left; gap: 16px; padding: 15px 12px; margin-bottom: 6px; background: none; border: 1px solid var(--line); }
.item:hover:not(:disabled) { background: #f6f8ef; border-color: #c5d2b5; }
.item-body { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.text { font-size: 14px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }
.source { font-size: 12px; color: #626f58; overflow-wrap: anywhere; }
.time { display: flex; align-items: center; gap: 5px; font-size: 11px; color: #626f58; }
.sample { color: #856013; font-size: 11px; }
img { width: 100px; height: 130px; object-fit: contain; background: var(--soft); border-radius: 6px; }
.empty { text-align: center; padding: 30px 10px; color: #626f58; background: #fafbf7; border: 1px dashed var(--line); border-radius: 8px; }
.empty p { margin: 10px 0 5px; font-size: 13px; }
.empty span { font-size: 12px; line-height: 1.8; }
@media (max-width: 760px) { .record-content { padding: 16px; } header { flex-wrap: wrap; } img { width: 65px; height: 90px; } .item { gap: 10px; padding: 12px 8px; } .time { flex-wrap: wrap; } }
</style>
