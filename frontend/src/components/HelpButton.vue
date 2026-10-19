<script setup>
defineProps({ label: { type: String, required: true } })
defineEmits(['click'])
</script>
<template><button type="button" class="help-button" :aria-label="`${label}帮助`" title="查看使用说明" @click="$emit('click')">?</button></template>
<style scoped>.help-button { width: 24px; height: 24px; min-height: 24px; padding: 0; border-radius: 50%; background: #edf2ff; color: #3159cb; font-weight: 700; flex: 0 0 auto; }</style>
