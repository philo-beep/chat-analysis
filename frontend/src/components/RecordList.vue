<!-- 历史列表，A 负责 -->
<script setup>
defineProps({
  records: { type: Array, default: () => [] },
})

defineEmits(['select', 'refresh'])
</script>

<template>
  <section class="record-list">
    <header>
      <h2>历史记录</h2>
      <button class="ghost" @click="$emit('refresh')">刷新</button>
    </header>
    <p v-if="!records.length" class="empty">还没有记录</p>
    <ul>
      <li v-for="record in records" :key="record.id">
        <button class="item" @click="$emit('select', record)">
          <span class="title">{{ record.title || '未命名' }}</span>
          <span class="time">{{ record.created_at }}</span>
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
ul {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
}
.item {
  width: 100%;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  cursor: pointer;
  background: none;
  border: none;
}
.time {
  font-size: 12px;
  color: #6b7280;
}
.empty {
  color: #6b7280;
  font-size: 14px;
}
</style>
