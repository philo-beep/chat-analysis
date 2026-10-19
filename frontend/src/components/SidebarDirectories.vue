<script setup>
import AppIcon from './AppIcon.vue'
import { directorySections } from '../navigation.js'

defineProps({
  section: { type: String, default: 'workspace' },
  counts: { type: Object, default: null },
  disabled: { type: Boolean, default: false },
  recordId: { type: Number, default: null },
  recordTitle: { type: String, default: '' },
  scope: { type: String, default: 'current' },
})
defineEmits(['navigate', 'scope'])
</script>

<template>
  <nav aria-label="内容目录" class="directories">
    <div class="scope-controls" role="group" aria-label="目录数据范围">
      <button :disabled="disabled || !recordId" :aria-pressed="scope === 'current'" @click="$emit('scope', 'current')">当前聊天</button>
      <button :disabled="disabled" :aria-pressed="scope === 'all'" @click="$emit('scope', 'all')">全部记录汇总</button>
    </div>
    <p class="context" :title="scope === 'current' ? recordTitle : ''">{{ scope === 'current' ? (recordId ? `当前：${recordTitle}` : '请先选择或分析一份聊天') : '最近 100 条记录汇总' }}</p>
    <section v-if="section !== 'workspace'" class="record-list">
      <button class="directory" :disabled="disabled" @click="$emit('navigate', 'workspace')">
        <AppIcon name="clock" :size="14" /><span>历史记录</span>
      </button>
    </section>
    <section class="record-list">
      <button class="directory" :class="{ selected: section === 'calendar' || section === 'calendar/gantt' }" :aria-current="section === 'calendar' || section === 'calendar/gantt' ? 'page' : undefined" :disabled="disabled" @click="$emit('navigate', 'calendar')">
        <AppIcon name="calendar" :size="14" /><span>日程计划</span>
      </button>
    </section>
    <section v-for="item in directorySections" :key="item.key" class="record-list">
      <button class="directory" :class="{ selected: section === item.key }" :aria-current="section === item.key ? 'page' : undefined" :disabled="disabled || (scope === 'current' && !recordId)" @click="$emit('navigate', item.key)">
        <AppIcon :name="item.icon" :size="14" /><span>{{ item.label }}</span>
        <span v-if="counts" class="count">{{ counts[item.key] }}</span>
      </button>
    </section>
  </nav>
</template>

<style scoped>
.directories { flex-shrink: 0; margin-bottom: 20px; }
.scope-controls { display: flex; gap: 4px; padding: 0 4px; }
.scope-controls button { flex: 1; min-height: 30px; padding: 5px 6px; background: transparent; border: 1px solid #dce3d1; color: #607253; font-size: 10px; }
.scope-controls button[aria-pressed="true"] { background: #e1e8d5; border-color: #cbd6bc; color: #354b2d; }
.scope-controls button:hover:not(:disabled) { background: #e9eddf; }
.context { font-size: 10px; line-height: 1.7; color: #65735c; margin: 8px 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.record-list { margin-bottom: 6px; }
.directory { width: 100%; justify-content: flex-start; padding: 10px 9px; min-height: 36px; font-size: 11px; font-weight: 500; color: #607253; background: none; border: 1px solid transparent; }
.directory:hover:not(:disabled) { background: #e9eddf; border-color: #e9eddf; }
.directory.selected { background: #e1e8d5; border-color: #cbd6bc; color: #354b2d; }
.count { font-size: 10px; margin-left: auto; background: #e6eadc; padding: 1px 6px; border-radius: 4px; color: #526247; }
@media (max-width: 760px) { .directories { display: flex; flex-wrap: wrap; gap: 4px; margin: 12px 0 0; } .scope-controls { width: 100%; } .context { width: 100%; margin: 4px; } .record-list { margin: 0; } .directory { padding: 8px; } }
</style>
