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
})
defineEmits(['select', 'refresh'])
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
            <span class="item-body"><span class="text">{{ item.text }}</span><span v-if="item.isSample" class="sample">开发样例</span><span class="source">来源：{{ item.title }} · #{{ item.recordId }}</span><span class="time"><AppIcon name="clock" :size="11" />{{ item.createdAt }} · 打开来源记录</span></span>
          </button>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.record-content { padding: 24px; }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 18px; }
h1 { font-size: 22px; margin-bottom: 10px; color: var(--ink); }
h1 span { font-size: 12px; margin-left: 8px; background: #edf2ff; color: #657eaf; padding: 3px 8px; border-radius: 4px; }
.hint { margin-bottom: 6px; }
.scope { font-size: 11px; }
.items { list-style: none; padding: 0; margin: 0; }
.item { width: 100%; justify-content: flex-start; align-items: flex-start; text-align: left; gap: 16px; padding: 15px 12px; margin-bottom: 6px; background: none; border: 1px solid #e5eaf2; }
.item:hover:not(:disabled) { background: #f3f6fc; border-color: #b9c8e6; }
.item-body { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.text { font-size: 14px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }
.source { font-size: 12px; color: #65758f; overflow-wrap: anywhere; }
.time { display: flex; align-items: center; gap: 5px; font-size: 11px; color: #758197; }
.sample { color: #946018; font-size: 11px; }
img { width: 100px; height: 130px; object-fit: contain; background: #f3f5f9; border-radius: 6px; }
.empty { text-align: center; padding: 30px 10px; color: #758197; background: #fafbfd; border: 1px dashed #e5eaf2; border-radius: 8px; }
.empty p { margin: 10px 0 5px; font-size: 13px; }
.empty span { font-size: 12px; line-height: 1.8; }
@media (max-width: 760px) { .record-content { padding: 16px; } header { flex-wrap: wrap; } img { width: 65px; height: 90px; } .item { gap: 10px; padding: 12px 8px; } .time { flex-wrap: wrap; } }
</style>
