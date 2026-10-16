<!-- 聊天输入，A 负责 -->
<script setup>
import { ref } from 'vue'

defineProps({
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['submit'])
const text = ref('')

function submit() {
  const value = text.value.trim()
  if (!value) return
  emit('submit', value)
}
</script>

<template>
  <section class="chat-input">
    <textarea
      v-model="text"
      rows="6"
      placeholder="把聊天原文粘贴到这里，例如：我们想定制 100 件文化衫"
    />
    <div class="actions">
      <button :disabled="loading || !text.trim()" @click="submit">
        {{ loading ? '分析中…' : '开始分析' }}
      </button>
      <button class="ghost" :disabled="loading" @click="text = ''">清空</button>
    </div>
  </section>
</template>

<style scoped>
textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  font: inherit;
}
.actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
button {
  padding: 8px 16px;
  cursor: pointer;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
