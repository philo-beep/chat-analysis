<script setup>
import { ref } from 'vue'
import { login, register } from '../api.js'

defineProps({ notice: { type: String, default: '' } })
const emit = defineEmits(['authenticated'])
const mode = ref('login')
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
const message = ref('')

function switchMode() {
  if (busy.value) return
  mode.value = mode.value === 'login' ? 'register' : 'login'
  password.value = ''
  error.value = ''
  message.value = ''
}

async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    if (mode.value === 'register') {
      await register(username.value.trim(), password.value)
      password.value = ''
      mode.value = 'login'
      message.value = '注册成功，请使用刚设置的账号和密码登录。'
    } else {
      const data = await login(username.value.trim(), password.value)
      password.value = ''
      emit('authenticated', data)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '请求失败，请重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="card login-card">
      <h1>客有数 · {{ mode === 'login' ? '登录' : '注册' }}</h1>
      <p>注册后可分析客户聊天并管理自己的记录。</p>
      <p v-if="notice" role="status">{{ notice }}</p>
      <form @submit.prevent="submit">
        <label for="auth-username">用户名</label>
        <input id="auth-username" v-model="username" name="username" autocomplete="username" required minlength="3" maxlength="64" :disabled="busy" />
        <label for="auth-password">密码</label>
        <input id="auth-password" v-model="password" name="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required maxlength="128" :disabled="busy" />
        <p v-if="mode === 'register'" class="hint">请设置较长且不重复使用的密码。具体格式由服务端校验。</p>
        <button type="submit" class="primary" :disabled="busy">{{ busy ? '处理中…' : mode === 'login' ? '登录' : '注册' }}</button>
        <button type="button" :disabled="busy" @click="switchMode">{{ mode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}</button>
      </form>
      <p v-if="message" class="success" role="status">{{ message }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>
  </main>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.login-card { width: min(100%, 420px); padding: 28px; }
h1 { font-size: 23px; }
p { line-height: 1.7; }
form { display: grid; gap: 12px; }
input { width: 100%; }
</style>
