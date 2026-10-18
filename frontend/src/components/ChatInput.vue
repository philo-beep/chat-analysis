<!-- 聊天输入，A 负责 -->
<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'

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
  const mime = file.type.toLowerCase()
  const supported = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'].includes(mime)
    || (!mime && /\.(png|jpe?g|webp)$/i.test(file.name))
  if (!supported) {
    inputError.value = '仅支持 PNG、JPEG、WebP 聊天截图，请转换格式后上传'
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    inputError.value = '图片不能超过 10 MiB'
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
  <section class="chat-input card">
    <header class="input-heading"><div class="section-title"><span class="section-icon"><AppIcon name="message" /></span><div><h2>整理客户沟通</h2><p>添加聊天内容，开始一次需求分析</p></div></div><button type="button" class="demo-button ghost" :disabled="props.loading" @click="fillDemo"><AppIcon name="spark" :size="14" />填入演示样例</button></header>
    <div class="input-body">
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
        <input type="file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp" :disabled="props.loading" @change="onFileChange" />
      </label>
      <button v-if="image" type="button" class="file-name" :disabled="props.loading" @click="removeImage">
        {{ image.name }} ×
      </button>
      <span class="hint">PNG / JPG / WebP · 最大 10 MiB</span>
    </div>
    <img v-if="imageUrl" class="preview" :src="imageUrl" alt="聊天截图预览" />
    <p v-if="inputError" class="input-error" role="alert">{{ inputError }}</p>
    <div class="actions">
      <button type="button" class="primary" :disabled="props.loading" @click="submit">
        <span v-if="props.loading" class="spinner" aria-hidden="true"></span><AppIcon v-else name="spark" :size="16" />
        {{ props.loading ? '分析中…' : '开始分析' }}
      </button>
      <button type="button" class="ghost" :disabled="props.loading" @click="clear">清空</button>
      <span class="input-meta">{{ text.length ? `${text.length} 字` : '也可直接粘贴聊天截图' }}</span>
    </div>
    <p v-if="props.loading" class="loading-note" role="status">正在整理沟通内容，截图识别可能需要更长时间，请稍候。</p>
    </div>
    <footer class="input-footer"><AppIcon name="shield" :size="13" /><span>本地处理，保留原文依据</span><span class="shortcut">Ctrl/Cmd + Shift + D 填充演示样例</span></footer>
  </section>
</template>

<style scoped>
.chat-input { overflow: hidden; }
.input-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 21px 26px; border-bottom: 1px solid var(--line); }
.input-heading h2 { margin: 0 0 4px; font-size: 16px; color: var(--ink); font-weight: 600; }
.input-heading p { margin: 0; color: var(--muted); font-size: 11px; }
.demo-button { border-color: transparent; color: #667b9e; font-size: 12px; padding: 6px 0 6px 10px; white-space: nowrap; }
.input-body { padding: 22px 26px; }
.customer-label { display: block; margin: 19px 0 8px; font-size: 12px; font-weight: 600; color: #43516a; }
.customer-label:first-child { margin-top: 0; }
.customer-name { max-width: 440px; }
.role-hint { margin: 0 0 10px; color: #8a96a9; font-size: 11px; line-height: 1.8; }
textarea { min-height: 160px; background: #fcfdff; line-height: 1.9; }
.upload-row { margin-top: 12px; display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.upload-button { display: inline-flex; align-items: center; border: 1px dashed #b8c7df; border-radius: 7px; padding: 8px 13px; color: #577299; background: #f9fbff; font-size: 12px; position: relative; cursor: pointer; overflow: hidden; }
.upload-button:hover { border-color: var(--brand); }
.upload-button input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.file-name { max-width: 100%; overflow-wrap: anywhere; font-size: 11px; background: #edf2fc; border: 0; }
.upload-row .hint { font-size: 10px; }
.preview { display: block; max-width: min(100%, 420px); max-height: 240px; margin-top: 14px; border: 1px solid var(--line); border-radius: 8px; }
.actions { border-top: 1px solid #f0f3f8; padding-top: 19px; margin-top: 21px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.actions .primary { min-width: 136px; min-height: 42px; }
.actions .ghost { border-color: transparent; color: #8290a5; }
.input-meta { color: #929db0; font-size: 11px; margin-left: auto; }
.input-footer { display: flex; align-items: center; gap: 6px; padding: 12px 26px; background: #fafbfd; border-top: 1px solid var(--line); color: #8a98ad; font-size: 10px; }
.shortcut { margin-left: auto; }
.loading-note { color: #5c76a9; font-size: 12px; margin: 12px 0 0; line-height: 1.6; }
.spinner { width: 14px; height: 14px; border: 2px solid #ffffff66; border-top-color: #fff; border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) { .input-heading { padding: 18px; flex-wrap: wrap; } .input-body { padding: 18px; } .input-heading p { font-size: 10px; } .demo-button { padding: 0; min-height: 24px; margin-left: 46px; } .input-meta { flex-basis: 100%; margin: 0; } .input-footer { padding: 12px 18px; flex-wrap: wrap; } .shortcut { display: none; } }
</style>
