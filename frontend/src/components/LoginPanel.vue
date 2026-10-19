<script setup>
import { nextTick, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import WelcomePanel from './WelcomePanel.vue'
import AssistantScene from './AssistantScene.vue'
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
const stage = ref('welcome')
const motionPaused = ref(false)

async function unlockAssistant() {
  stage.value = 'auth'
  await nextTick()
  document.getElementById('auth-username')?.focus({ preventScroll: true })
}

function returnWelcome() {
  if (busy.value) return
  stage.value = 'welcome'
  password.value = ''
}

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
  <WelcomePanel v-if="stage === 'welcome'" :paused="motionPaused" :notice="notice" @unlock="unlockAssistant" @toggle-motion="motionPaused = !motionPaused" />
  <main v-else class="login-page" :class="{ 'motion-paused': motionPaused }">
    <div class="auth-glow" aria-hidden="true"></div>
    <header class="auth-header">
      <button type="button" class="return-welcome" :disabled="busy" @click="returnWelcome"><span aria-hidden="true">←</span> 返回客有数</button>
      <button type="button" class="motion-button" :aria-pressed="motionPaused" @click="motionPaused = !motionPaused">{{ motionPaused ? '继续动效' : '暂停动效' }}</button>
    </header>
    <div class="auth-layout">
    <section class="auth-story" aria-labelledby="auth-story-title">
      <div class="story-eyebrow"><span></span>YOUR BUSINESS, WITH CLARITY</div>
      <h2 id="auth-story-title">客户的每一句话，<br />都值得<span>好好跟进。</span></h2>
      <p class="story-description">少一点反复翻找，多一点有准备的回应。<br />让你的智能助手，把零散沟通变成清晰的行动。</p>
      <AssistantScene :paused="motionPaused" compact />
      <p class="scene-caption">产品流程示意 · 由你确认，帮你推进</p>
      <div class="story-values"><span><AppIcon name="message" :size="14" />整理客户沟通</span><span><AppIcon name="check" :size="14" />看清下一步</span><span><AppIcon name="calendar" :size="14" />安排跟进日程</span></div>
    </section>
    <section class="card login-card">
      <div class="login-brand"><span class="login-mark"><AppIcon name="leaf" :size="23" /></span><span>客有数<span class="brand-dot">.</span><small>让好生意，自然发生</small></span></div>
      <div class="form-eyebrow">{{ mode === 'login' ? 'WELCOME BACK' : 'A CLEARER WAY TO WORK' }}</div>
      <h1>客有数 · {{ mode === 'login' ? '登录' : '注册' }}</h1>
      <p class="login-intro">{{ mode === 'login' ? '欢迎回来，继续推进你的下一笔好生意。' : '创建账号，让客户沟通与日程有条不紊。' }}</p>
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
      <div class="form-footer"><AppIcon name="shield" :size="14" /><span>登录后管理你的聊天记录与个人日程</span></div>
    </section>
    </div>
    <footer class="auth-footer"><span>客有数 · 客户沟通智能助手</span><span>每次沟通，都更进一步。</span></footer>
  </main>
</template>

<style scoped>
.login-page { position: relative; isolation: isolate; overflow: hidden; min-height: 100svh; padding: 26px max(28px, calc((100vw - 1280px) / 2)); background: #102e2b; color: #f5f5e9; display: flex; flex-direction: column; }
.login-page::before { content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none; background-image: linear-gradient(#bcd3b505 1px, transparent 1px), linear-gradient(90deg, #bcd3b505 1px, transparent 1px); background-size: 64px 64px; }
.auth-glow { position: absolute; width: 850px; height: 850px; left: -300px; top: -180px; z-index: -1; pointer-events: none; background: radial-gradient(circle, #4c76553d, transparent 65%); animation: auth-drift 18s ease-in-out infinite; }
.auth-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }.return-welcome, .motion-button { border: 1px solid #b9d1b42a; color: #c5d4c8; background: #ffffff04; font-size: 12px; padding: 9px 13px; border-radius: 25px; }.return-welcome span { margin-right: 7px; }.return-welcome:hover:not(:disabled), .motion-button:hover { background: #ffffff0d; }
.auth-layout { width: 100%; max-width: 1110px; margin: auto; padding: 54px 0; display: grid; grid-template-columns: minmax(0, 1.13fr) minmax(0, .87fr); gap: 80px; align-items: center; }
.auth-story { min-width: 0; }.story-eyebrow { display: flex; align-items: center; gap: 9px; color: #b9cbaa; font-size: 10px; letter-spacing: 2px; }.story-eyebrow > span { width: 5px; height: 5px; background: #cdd4a3; border-radius: 50%; }.auth-story h2 { color: #f2f4e8; font-size: clamp(31px, 3.3vw, 46px); font-weight: 550; line-height: 1.4; letter-spacing: -1.5px; margin: 24px 0 17px; }.auth-story h2 span { color: #ded5a3; }.story-description { font-size: 13px; color: #b0c5b9; line-height: 1.9; margin-bottom: 18px; }.scene-caption { font-size: 10px; color: #8da798; text-align: center; margin: 19px 0; }.story-values { display: flex; justify-content: space-between; gap: 10px; padding-top: 18px; border-top: 1px solid #bcd0b421; }.story-values > span { display: flex; align-items: center; gap: 6px; color: #b9cabb; font-size: 10px; }
.login-card { width: 100%; padding: 36px; color: #193b32; background: #fbfcf7; border: 1px solid #f6f8ec; border-radius: 20px; box-shadow: 0 25px 80px #031a232b; }
.login-brand { display: flex; align-items: center; gap: 12px; color: #173c33; font-size: 26px; font-weight: 650; margin-bottom: 40px; }.login-mark { width: 44px; height: 44px; display: grid; place-items: center; color: #e2deb3; background: #204638; border-radius: 13px; }.brand-dot { color: #91a375; }.login-brand small { display: block; font-size: 10px; font-weight: 400; letter-spacing: 2px; color: #768571; margin-top: 4px; }
.form-eyebrow { font-size: 9px; letter-spacing: 2px; color: #899783; margin-bottom: 10px; }h1 { color: #173c33; font-size: 25px; font-weight: 600; margin: 0 0 12px; }p { line-height: 1.8; }.login-intro { font-size: 12px; color: #73806f; margin-bottom: 26px; }
form { display: grid; gap: 10px; }label { font-size: 12px; font-weight: 600; margin-top: 8px; }input { width: 100%; min-height: 47px; background: #f5f7ef; border: 1px solid #dce3d4; border-radius: 9px; color: #173c33; padding: 10px 13px; }input:focus { outline: 2px solid #92ab80; outline-offset: 2px; }.hint { display: block; color: #6d7c65; font-size: 11px; line-height: 1.7; }form .primary { margin-top: 16px; min-height: 46px; color: #f6f4e6; background: #244e3d; border-color: #244e3d; border-radius: 9px; font-size: 13px; }form .primary:hover:not(:disabled) { background: #326147; }
.switch-mode { background: transparent; border-color: transparent; color: #587547; min-height: 38px; font-size: 12px; }.switch-mode:hover:not(:disabled) { background: #edf2e4; }.error { color: #a5372d; font-size: 12px; }.success { color: #366344; padding: 10px 12px; background: #edf3e5; border-radius: 8px; font-size: 12px; }.form-footer { display: flex; align-items: center; justify-content: center; gap: 7px; font-size: 10px; color: #87917f; border-top: 1px solid #e7ebdf; margin-top: 22px; padding-top: 20px; line-height: 1.6; }.auth-footer { display: flex; justify-content: space-between; gap: 15px; color: #829f90; font-size: 10px; padding: 4px 0; }.motion-paused * { animation-play-state: paused !important; }
@keyframes auth-drift { 0%, 100% { transform: translate3d(0,0,0); } 50% { transform: translate3d(35px,25px,0); } }
.auth-layout { animation:auth-enter .45s ease-out both; }
.motion-paused .auth-layout { animation:none; }
@keyframes auth-enter { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
@media (max-width: 1050px) { .auth-layout { gap: 35px; }.login-card { padding: 30px; }.auth-story h2 { font-size: 35px; }.story-values { flex-wrap: wrap; justify-content: flex-start; gap: 14px; } }
@media (max-width: 760px) { .login-page { padding: 20px; }.auth-layout { max-width: 440px; grid-template-columns: minmax(0, 1fr); padding: 30px 0; gap: 24px; }.auth-story h2 { font-size: 28px; margin: 14px 0 10px; }.story-eyebrow { font-size: 9px; letter-spacing: 1px; }.story-description { font-size: 12px; margin-bottom: 0; }.auth-story :deep(.assistant-scene), .scene-caption, .story-values { display: none; }.login-card { padding: 28px; border-radius: 16px; }.login-brand { margin-bottom: 27px; }.auth-footer { font-size: 9px; flex-wrap: wrap; } }
@media (max-width: 370px) { .login-page { padding: 16px; }.login-card { padding: 22px 18px; }.auth-story h2 { font-size: 25px; }.form-footer { font-size: 9px; } }
@media (prefers-reduced-motion: reduce) { *, *::before { animation: none !important; transition: none !important; } }
</style>
