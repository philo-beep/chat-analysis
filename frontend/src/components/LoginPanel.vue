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
const usernameError = ref('')
const message = ref('')

function switchMode() {
  if (busy.value) return
  mode.value = mode.value === 'login' ? 'register' : 'login'
  password.value = ''
  error.value = ''
  usernameError.value = ''
  message.value = ''
}

async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  usernameError.value = ''
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
    if (mode.value === 'register' && e.status === 409) {
      usernameError.value = '用户名已存在，请更换用户名。'
    } else {
      error.value = e instanceof Error ? e.message : '请求失败，请重试'
    }
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
        <input id="auth-username" v-model="username" name="username" autocomplete="username" required minlength="3" maxlength="64" :disabled="busy" :aria-invalid="!!usernameError" :aria-describedby="usernameError ? 'auth-username-error' : mode === 'register' ? 'auth-username-hint' : undefined" @input="usernameError = ''" />
        <small v-if="mode === 'register'" id="auth-username-hint" class="hint">3–64 个字符，可用字母、数字、汉字、下划线、点和短横线。英文字母不区分大小写，用户名不可重复。</small>
        <p v-if="usernameError" id="auth-username-error" class="error" role="alert">{{ usernameError }}</p>
        <label for="auth-password">密码</label>
        <input id="auth-password" v-model="password" name="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required :minlength="mode === 'register' ? 10 : undefined" maxlength="128" :disabled="busy" :aria-describedby="mode === 'register' ? 'auth-password-hint' : undefined" />
        <small v-if="mode === 'register'" id="auth-password-hint" class="hint">密码长度为 10–128 个字符，不强制要求大小写或特殊符号；建议组合使用字母、数字和符号。</small>
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
.hint { display: block; color: #64748b; font-size: 12px; line-height: 1.6; }
</style>
