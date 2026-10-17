<!-- 聊天输入，A 负责 -->
<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['submit'])
const text = ref('')
const customerName = ref('')
const image = ref(null)
const imageUrl = ref('')
const inputError = ref('')

const demoText = '客户：我们想定制100件文化衫，总预算3000元，10月30日前收到，需要你们提供设计。'

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
  if (props.loading) return
  customerName.value = '演示客户'
  text.value = demoText
  inputError.value = ''
}

function handleShortcut(event) {
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'd') {
    event.preventDefault()
    fillDemo()
  }
}

onMounted(() => window.addEventListener('keydown', handleShortcut))
onUnmounted(() => {
  window.removeEventListener('keydown', handleShortcut)
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
})

function submit() {
  if (props.loading) return
  const value = text.value.trim()
  if (!value && !image.value) {
    inputError.value = '请粘贴聊天原文或上传聊天截图'
    return
  }
  inputError.value = ''
  const name = customerName.value.trim().replace(/[\r\n]+/g, ' ')
  const originalText = name ? `客户名称：${name}\n${text.value}` : text.value
  emit('submit', { text: originalText, image: image.value })
}

function removeImage() {
  image.value = null
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = ''
}

function clear() {
  customerName.value = ''
  text.value = ''
  removeImage()
  inputError.value = ''
}
</script>

<template>
  <section class="chat-input">
    <label class="customer-label" for="customer-name">客户名称（可选）</label>
    <input
      id="customer-name"
      v-model="customerName"
      class="customer-name"
      placeholder="例如：张先生 / 某某公司"
      maxlength="100"
      :disabled="props.loading"
    />
    <label class="customer-label" for="chat-text">聊天原文</label>
    <p id="role-hint" class="role-hint">多轮聊天请按发言顺序逐行填写：客户：… / 商家：…；仅有客户原话也可以直接粘贴。</p>
    <textarea
      id="chat-text"
      v-model="text"
      rows="6"
      placeholder="客户：想定制一批文化衫。&#10;商家：预计多少件，有预算要求吗？&#10;客户：大概100件，预算三四千。"
      aria-describedby="role-hint"
      :disabled="props.loading"
      @paste="onPaste"
    />
    <div class="upload-row">
      <label class="upload-button">
        上传聊天截图
        <input type="file" accept="image/*" :disabled="props.loading" @change="onFileChange" />
      </label>
      <button v-if="image" type="button" class="file-name" :disabled="props.loading" @click="removeImage">
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
.customer-label {
  display: block;
  margin: 10px 0 6px;
  font-size: 14px;
  font-weight: 600;
}
.customer-name {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font: inherit;
}
.role-hint {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 13px;
}
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
