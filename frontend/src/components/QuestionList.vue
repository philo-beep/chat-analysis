<script setup>
import RecordContentList from './RecordContentList.vue'
defineOptions({ inheritAttrs: false })
</script>

<template>
  <RecordContentList v-bind="$attrs" title="待确认事项" description="查看已保存的待确认问题；是否已经解决，需结合来源记录人工核对。" empty-text="这些记录中还没有待确认事项" />
</template>
