<script setup>
import RecordContentList from './RecordContentList.vue'
defineOptions({ inheritAttrs: false })
</script>

<template>
  <RecordContentList v-bind="$attrs" title="建议待办" description="查看已保存的行动建议；当前尚不记录负责人、截止时间或完成状态。" empty-text="这些记录中还没有建议待办" />
</template>
