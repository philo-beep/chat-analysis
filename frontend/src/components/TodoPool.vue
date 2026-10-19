<script setup>
import HelpButton from './HelpButton.vue'
defineProps({ items: { type: Array, default: () => [] }, disabled: Boolean })
defineEmits(['create', 'open', 'complete', 'help'])
</script>
<template><section class="pool" aria-label="无 DDL 待办池"><header><h2>无 DDL 待办池 <HelpButton label="无 DDL 待办池" @click="$emit('help','todo')" /></h2><button :disabled="disabled" @click="$emit('create')">+ 新增待办</button></header><p class="hint">暂未确定截止日期的事情先收进这里，排期后进入日历。</p><p v-if="!items.length" class="empty">没有未排期的待办，去加一个吧</p><ul v-else><li v-for="item in items" :key="item.id"><button class="title" @click="$emit('open',item)">{{ item.title }}</button><div class="actions"><button :disabled="disabled" @click="$emit('open',item)">设 DDL</button><button :disabled="disabled" @click="$emit('complete',item)">完成任务</button></div></li></ul></section></template>
<style scoped>.pool{border-top:1px solid var(--line);padding-top:22px;margin-top:24px}header,h2,.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}header{justify-content:space-between;margin-bottom:8px}h2{font-size:17px;margin:0}.empty{color:var(--muted);font-size:13px;background:#f7f9f2;border:1px dashed var(--line);padding:22px;text-align:center}ul{padding:0;list-style:none}li{border-bottom:1px solid var(--line);padding:12px 0;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.title{border:0;background:none;padding:0;text-align:left;justify-content:flex-start;white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%;flex:1;min-width:120px}.actions button{font-size:12px;padding:6px 9px}@media(max-width:560px){.actions{width:100%}}
.pool { border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: var(--canvas); }
h2 { color: var(--ink); font-size: 16px; }
.empty { border-radius: 10px; background: var(--surface); line-height: 1.7; }
ul { margin-bottom: 0; }
li:last-child { border-bottom: 0; }
.title { color: var(--ink); line-height: 1.7; }
@media(max-width:560px) { .pool { padding: 12px; } .actions { gap: 8px; } }
</style>
