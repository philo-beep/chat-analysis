<script setup>
import { onMounted, onBeforeUnmount, ref, nextTick } from 'vue'
const props = defineProps({ title: String, busy: Boolean })
const emit = defineEmits(['close'])
const box = ref(null)
let previous, previousDialog
function keys(event) {
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!props.busy) emit('close') }
  if (event.key !== 'Tab') return
  const nodes = [...box.value.querySelectorAll('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex="0"]')].filter(n => n.getClientRects().length)
  if (!nodes.length) { event.preventDefault(); box.value.focus(); return }
  if (event.shiftKey && (document.activeElement === nodes[0] || document.activeElement === box.value)) { event.preventDefault(); nodes.at(-1).focus() }
  else if (!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0].focus() }
}
onMounted(async () => {
  previous = document.activeElement
  previousDialog = previous?.closest('[role="dialog"]')
  await nextTick()
  box.value.focus()
  if (previousDialog) { previousDialog.inert = true; previousDialog.setAttribute('aria-hidden', 'true') }
})
onBeforeUnmount(() => {
  if (previousDialog?.isConnected) { previousDialog.inert = false; previousDialog.removeAttribute('aria-hidden') }
  if (previous?.isConnected) previous.focus()
})
</script>
<template><Teleport to="body"><div class="calendar-overlay" @click.self="!busy && $emit('close')"><section ref="box" class="calendar-dialog card" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1" @keydown="keys"><header><h2>{{ title }}</h2><button aria-label="关闭弹窗" :disabled="busy" @click="$emit('close')">×</button></header><slot /></section></div></Teleport></template>
<style scoped>.calendar-overlay { position: fixed; inset: 0; background: #13233c88; z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 16px; }.calendar-dialog { width: min(560px, 100%); max-height: calc(100dvh - 32px); overflow-y: auto; padding: 24px; outline: none; }header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:18px; }h2{ font-size:19px; margin:0; }header button { min-width:32px; padding:4px; }@media(max-width:500px){.calendar-dialog{padding:16px}}</style>
