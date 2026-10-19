<script setup>
import AppIcon from './AppIcon.vue'
import { directorySections } from '../navigation.js'

defineProps({
  section: { type: String, default: 'workspace' },
  counts: { type: Object, default: null },
  disabled: { type: Boolean, default: false },
})
defineEmits(['navigate'])
</script>

<template>
  <nav aria-label="内容目录" class="directories">
    <section v-if="section !== 'workspace'" class="record-list">
      <button class="directory" :disabled="disabled" @click="$emit('navigate', 'workspace')">
        <AppIcon name="clock" :size="14" /><span>历史记录</span>
      </button>
    </section>
    <section v-for="item in directorySections" :key="item.key" class="record-list">
      <button class="directory" :class="{ selected: section === item.key }" :aria-current="section === item.key ? 'page' : undefined" :disabled="disabled" @click="$emit('navigate', item.key)">
        <AppIcon :name="item.icon" :size="14" /><span>{{ item.label }}</span>
        <span v-if="counts" class="count">{{ counts[item.key] }}</span>
      </button>
    </section>
  </nav>
</template>

<style scoped>
.directories { flex-shrink: 0; margin-bottom: 20px; }
.record-list { margin-bottom: 6px; }
.directory { width: 100%; justify-content: flex-start; padding: 10px 9px; min-height: 36px; font-size: 11px; font-weight: 500; color: #97a8c3; background: none; border: 1px solid transparent; }
.directory:hover:not(:disabled) { background: #ffffff08; border-color: #ffffff08; }
.directory.selected { background: #25406480; border-color: #5576ae45; color: #e2ecff; }
.count { font-size: 10px; margin-left: auto; background: #ffffff0c; padding: 1px 6px; border-radius: 4px; color: #8fa5c6; }
@media (max-width: 760px) { .directories { display: flex; flex-wrap: wrap; gap: 4px; margin: 12px 0 0; } .record-list { margin: 0; } .directory { padding: 8px; } }
</style>
