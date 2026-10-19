<script setup>
import RecordContentList from './RecordContentList.vue'
defineOptions({ inheritAttrs: false })
</script>

<template>
  <RecordContentList v-bind="$attrs" title="建议待办" description="查看聊天中已保存的行动建议；可加入日程计划的待办池，再安排截止日期和记录完成状态。" empty-text="这些记录中还没有建议待办" />
</template>
