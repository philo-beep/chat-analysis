<script setup>
import { ref } from 'vue'
import AppIcon from './AppIcon.vue'
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
      <div class="login-brand"><span class="login-mark"><AppIcon name="spark" :size="23" /></span><span>客有数<span class="brand-dot">.</span><small>让好生意，自然发生</small></span></div>
      <h1>客有数 · {{ mode === 'login' ? '登录' : '注册' }}</h1>
      <p class="login-intro">把沟通放进来，让需求清楚起来。<br />注册后可分析客户聊天并管理自己的记录。</p>
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
        <button type="button" class="switch-mode" :disabled="busy" @click="switchMode">{{ mode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}</button>
      </form>
      <p v-if="message" class="success" role="status">{{ message }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>
  </main>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; padding: 32px 20px; background: radial-gradient(ellipse at 15% 12%, #e8eddb 0, transparent 45%), radial-gradient(ellipse at 85% 88%, #f6efc9 0, transparent 38%), var(--canvas); }
.login-card { width: min(100%, 460px); padding: 34px; border: 1px solid var(--line); box-shadow: 0 16px 55px #4553340d; }
.login-brand { display: flex; align-items: center; gap: 12px; color: var(--ink); font-size: 24px; font-weight: 700; margin-bottom: 30px; }
.login-mark { width: 44px; height: 44px; display: grid; place-items: center; color: #fff; background: var(--brand); border-radius: 12px; }
.brand-dot { color: var(--brand); }
.login-brand small { display: block; font-size: 10px; font-weight: 400; letter-spacing: 2px; color: #626f58; margin-top: 4px; }
h1 { font-size: 21px; margin: 0 0 12px; }
p { line-height: 1.8; }
.login-intro { font-size: 12px; color: #626f58; margin-bottom: 24px; }
form { display: grid; gap: 10px; }
label { font-size: 12px; font-weight: 600; margin-top: 8px; }
input { width: 100%; min-height: 43px; background: #fdfdf8; }
.hint { display: block; color: #626f58; font-size: 12px; line-height: 1.7; }
form .primary { margin-top: 14px; min-height: 44px; }
.switch-mode { background: transparent; border-color: transparent; color: var(--brand); min-height: 38px; font-size: 12px; }
.switch-mode:hover:not(:disabled) { background: var(--soft); }
.error { color: #a5372d; }
.success { color: #366344; padding: 10px 12px; background: #edf3e5; border-radius: 8px; font-size: 12px; }
@media (max-width: 480px) { .login-card { padding: 26px 22px; } .login-brand { margin-bottom: 24px; } }
</style>
