<script setup>
import RecordContentList from './RecordContentList.vue'
defineOptions({ inheritAttrs: false })
</script>

<template>
  <RecordContentList v-bind="$attrs" title="聊天截图" description="查看已保存的聊天截图和转录摘要，点击可打开来源记录核对完整原图与原文。" empty-text="这些记录中还没有保存聊天截图" />
</template>
