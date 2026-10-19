<!-- 历史列表，A 负责 -->
<script setup>
import AppIcon from './AppIcon.vue'
import { directorySections } from '../navigation.js'
const props = defineProps({
  records: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  notice: { type: String, default: '' },
  selectedId: { type: Number, default: null },
  activeSection: { type: String, default: 'workspace' },
  allowDelete: { type: Boolean, default: false },
})

defineEmits(['select', 'refresh', 'shortcut', 'delete'])
</script>

<template>
  <section class="record-list">
    <header>
      <h2>历史记录 <span>{{ props.records.length }}</span></h2>
      <button class="ghost refresh-button" :aria-label="props.loading ? '加载中…' : '刷新'" :disabled="props.loading" @click="$emit('refresh')">
        <AppIcon name="refresh" :size="14" />
      </button>
    </header>
    <p v-if="props.notice" class="record-notice" role="status">{{ props.notice }}</p>
    <p v-if="props.error" class="error" role="alert">{{ props.error }}</p>
    <p v-else-if="props.loading && !props.records.length" class="empty">正在加载历史记录…</p>
    <div v-else-if="!props.records.length" class="empty"><AppIcon name="file" :size="27" /><p>还没有记录</p><span>完成分析后，需求单将保存在这里</span></div>
    <ul>
      <li v-for="record in props.records" :key="record.id">
        <div class="record-row">
          <button class="item" :class="{ selected: record.id === props.selectedId }" :aria-pressed="record.id === props.selectedId" :disabled="props.loading" @click="$emit('select', record)">
            <span class="title">{{ record.title || '未命名' }}</span>
            <span class="time"><AppIcon name="clock" :size="11" />{{ record.created_at }}</span>
          </button>
          <button v-if="props.allowDelete && record.can_delete === true" class="delete-record" type="button" :aria-label="`删除聊天记录：${record.title || '未命名'}`" :disabled="props.loading" @click="$emit('delete', record)">
            <AppIcon name="trash" :size="14" />
          </button>
        </div>
        <div v-if="record.id === props.selectedId" class="record-shortcuts" role="group" :aria-label="`${record.title || '未命名'}的快捷入口`">
          <button
            v-for="item in directorySections"
            :key="item.key"
            type="button"
            class="record-shortcut"
            :class="{ active: props.activeSection === item.key }"
            :aria-pressed="props.activeSection === item.key"
            :aria-label="`${record.title || '未命名'}：${item.label}`"
            :disabled="props.loading"
            @click="$emit('shortcut', { id: record.id, section: item.key })"
          >
            <AppIcon :name="item.icon" :size="12" />
            <span>{{ item.label }}</span>
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.record-list { min-height: 0; overflow-y: auto; margin-bottom: 20px; scrollbar-width: thin; scrollbar-color: #34496b transparent; }
header { display: flex; align-items: center; justify-content: space-between; margin: 0 9px 12px; }
h2 { margin: 0; font-size: 11px; font-weight: 500; color: #97a8c3; }
h2 span { font-size: 10px; margin-left: 7px; background: #ffffff0c; padding: 1px 6px; border-radius: 4px; color: #7187a8; }
.refresh-button { color: #8b9ebd; border: 0; padding: 3px; min-height: 24px; }
.refresh-button:hover:not(:disabled) { background: #ffffff0d; color: #d1dfff; }
ul { list-style: none; padding: 0; margin: 0; }
.record-row { display: flex; align-items: stretch; gap: 2px; }
.item { flex: 1; min-width: 0; width: auto; text-align: left; align-items: flex-start; display: flex; flex-direction: column; gap: 8px; padding: 13px 12px; margin-bottom: 4px; background: none; border: 1px solid transparent; color: #becbe0; }
.item:hover:not(:disabled) { background: #ffffff08; border-color: #ffffff08; }
.item.selected { background: #25406480; border-color: #5576ae45; color: #e2ecff; }
.delete-record { flex: 0 0 30px; align-self: center; min-width: 30px; min-height: 30px; padding: 5px; border: 0; background: transparent; color: #8b9ebd; }
.delete-record:hover:not(:disabled) { color: #ffaaa5; background: #ffffff0d; }
.record-notice { margin: 6px 8px; color: #a8d6c2; font-size: 10px; line-height: 1.5; }
.record-shortcuts { display: flex; flex-direction: column; gap: 3px; padding: 1px 8px 8px; }
.record-shortcut { display: flex; align-items: center; gap: 7px; width: 100%; min-height: 28px; padding: 5px 8px; border: 1px solid transparent; background: none; color: #91a7c8; text-align: left; font-size: 11px; }
.record-shortcut:hover:not(:disabled) { color: #d1dfff; background: #ffffff08; }
.record-shortcut.active { color: #e2ecff; background: #25406480; border-color: #5576ae45; }
.record-shortcut:focus-visible { outline: 2px solid #8baee8; outline-offset: 1px; }
.title { font-size: 12px; line-height: 1.7; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.time { display: flex; align-items: center; gap: 5px; font-size: 9px; color: #6f85a6; }
.empty { text-align: center; padding: 27px 10px; color: #536d93; background: #ffffff02; border: 1px dashed #ffffff0b; border-radius: 8px; margin: 0 4px; }
.empty p { margin: 10px 0 5px; font-size: 12px; color: #899bb6; }
.empty span { display: block; font-size: 10px; line-height: 1.9; color: #627a9c; }
@media (max-width: 760px) { .record-list { margin: 18px 0 0; max-height: 156px; } header { margin: 0 0 5px; } .empty { padding: 8px; text-align: left; border: 0; background: transparent; } .empty > svg, .empty span { display: none; } .empty p { margin: 0; font-size: 11px; } ul { display: flex; gap: 8px; overflow-x: auto; } li { min-width: 180px; max-width: 240px; flex-shrink: 0; } .item { padding: 8px; margin: 0; } .record-shortcuts { flex-direction: row; flex-wrap: wrap; gap: 3px; padding: 3px 4px 5px; } .record-shortcut { width: auto; min-height: 24px; padding: 3px 5px; gap: 4px; font-size: 10px; } }
</style>
