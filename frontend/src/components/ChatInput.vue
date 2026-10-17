<!-- 聊天输入，A 负责 -->
<script setup>
import { ref } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['submit'])
const text = ref('')
const image = ref(null)
const imageUrl = ref('')
const inputError = ref('')

const demoText = '我们想定制100件文化衫，总预算3000元，10月30日前收到，需要你们提供设计。'

function setImage(file) {
  inputError.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    inputError.value = '请上传 PNG、JPG 等图片格式的聊天截图'
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    inputError.value = '图片不能超过 10 MB'
    return
  }
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  image.value = file
  imageUrl.value = URL.createObjectURL(file)
}

function onFileChange(event) {
  setImage(event.target.files?.[0])
  event.target.value = ''
}

function onPaste(event) {
  const pastedImage = Array.from(event.clipboardData?.items || [])
    .find((item) => item.type.startsWith('image/'))
  if (pastedImage) {
    event.preventDefault()
    setImage(pastedImage.getAsFile())
  }
}

function fillDemo() {
  text.value = demoText
  inputError.value = ''
}

function submit() {
  const value = text.value.trim()
  if (!value && !image.value) {
    inputError.value = '请粘贴聊天原文或上传聊天截图'
    return
  }
  inputError.value = ''
  emit('submit', { text: value, image: image.value })
}

function clear() {
  text.value = ''
  image.value = null
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = ''
  inputError.value = ''
}
</script>

<template>
  <section class="chat-input">
    <textarea
      v-model="text"
      rows="6"
      placeholder="把聊天原文粘贴到这里，例如：我们想定制 100 件文化衫"
      :disabled="props.loading"
      @paste="onPaste"
      @keydown.ctrl.shift.d.prevent="fillDemo"
      @keydown.meta.shift.d.prevent="fillDemo"
    />
    <div class="upload-row">
      <label class="upload-button">
        上传聊天截图
        <input type="file" accept="image/*" :disabled="props.loading" @change="onFileChange" />
      </label>
      <button v-if="image" type="button" class="file-name" :disabled="props.loading" @click="clear">
        {{ image.name }} ×
      </button>
      <span class="hint">Ctrl/Cmd + Shift + D 填充演示样例</span>
    </div>
    <img v-if="imageUrl" class="preview" :src="imageUrl" alt="聊天截图预览" />
    <p v-if="inputError" class="input-error" role="alert">{{ inputError }}</p>
    <div class="actions">
      <button type="button" :disabled="props.loading" @click="submit">
        {{ props.loading ? '分析中…' : '开始分析' }}
      </button>
      <button type="button" class="ghost" :disabled="props.loading" @click="clear">清空</button>
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
.upload-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
}
.upload-button {
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  cursor: pointer;
}
.upload-button input {
  display: none;
}
.file-name {
  border: 0;
  background: #f1f5f9;
  color: #334155;
}
.hint {
  color: #64748b;
}
.preview {
  display: block;
  max-width: min(100%, 420px);
  max-height: 240px;
  margin-top: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}
.input-error {
  color: #dc2626;
  margin: 8px 0 0;
  font-size: 14px;
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
