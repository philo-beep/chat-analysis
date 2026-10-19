<script setup>
import { onMounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import AssistantScene from './AssistantScene.vue'
defineProps({ paused: Boolean, notice: { type: String, default: '' } })
const emit = defineEmits(['unlock', 'toggle-motion'])
const unlockButton = ref(null)
onMounted(() => unlockButton.value?.focus({ preventScroll: true }))
</script>

<template>
  <main class="welcome-page" :class="{ 'motion-paused': paused }">
    <div class="welcome-glow glow-one" aria-hidden="true"></div><div class="welcome-glow glow-two" aria-hidden="true"></div>
    <header class="welcome-header">
      <div class="welcome-brand"><span class="brand-symbol"><AppIcon name="leaf" :size="23" /></span><span>客有数<small>你的生意，心中有数</small></span></div>
      <button type="button" class="motion-button" :aria-pressed="paused" @click="emit('toggle-motion')"><span aria-hidden="true">{{ paused ? '▷' : 'Ⅱ' }}</span>{{ paused ? '继续动效' : '暂停动效' }}</button>
    </header>
    <section class="welcome-main">
      <div class="welcome-kicker"><span></span>为每一次客户沟通，留好下一步</div>
      <h1>把时间留给客户，<br />把琐事交给<span class="assistant-word">助手<svg viewBox="0 0 210 15" aria-hidden="true"><path d="M4 10 Q95 -2 204 8" /></svg></span></h1>
      <p class="welcome-description">从一句客户需求，到一次有准备的跟进。<br />客有数帮你整理对话、厘清需求、安排待办，让生意推进更从容。</p>
      <button ref="unlockButton" class="unlock-button" type="button" @click="emit('unlock')">点击解锁助手 <AppIcon name="arrow" :size="19" /></button>
      <p class="welcome-note">登录或创建账号，开启你的智能跟进工作台</p>
      <p v-if="notice" class="welcome-notice" role="status">{{ notice }}</p>
      <div class="welcome-showcase"><AssistantScene :paused="paused" /></div>
    </section>
    <footer class="welcome-footer">
      <div><span>01</span><strong>读懂沟通</strong><small>文字与聊天截图，一起整理</small></div>
      <div><span>02</span><strong>明确需求</strong><small>需求、疑问、回复，有据可循</small></div>
      <div><span>03</span><strong>推进跟进</strong><small>待办与日程，把下一步落地</small></div>
    </footer>
    <p class="welcome-caption">画面内容为产品流程示意 · 实际结果以你的客户对话为准</p>
  </main>
</template>

<style scoped>
.welcome-page { --entrance-ink: #102e2b; min-height: 100svh; overflow: hidden; position: relative; isolation: isolate; background: #102e2b; color: #f5f5e9; padding: 28px max(28px, calc((100vw - 1280px) / 2)); }
.welcome-page::before { content: ''; position: absolute; z-index: -1; inset: 0; background-image: linear-gradient(#bcd3b505 1px, transparent 1px), linear-gradient(90deg, #bcd3b505 1px, transparent 1px); background-size: 64px 64px; mask-image: linear-gradient(transparent, #000, transparent); pointer-events: none; }
.welcome-glow { position: absolute; z-index: -1; width: 650px; height: 650px; border-radius: 50%; background: radial-gradient(circle, #547d5933, transparent 68%); animation: drift 18s ease-in-out infinite; pointer-events: none; }.glow-one { top: -160px; right: -220px; }.glow-two { bottom: -300px; left: -280px; animation-delay: -9s; background: radial-gradient(circle, #c9bd7a16, transparent 68%); }
.welcome-header { display: flex; justify-content: space-between; align-items: center; position: relative; z-index: 2; }
.welcome-brand { color: #f7f4e7; text-decoration: none; display: inline-flex; align-items: center; gap: 11px; font-size: 24px; font-weight: 650; letter-spacing: 1px; }.brand-symbol { display: grid; place-items: center; width: 43px; height: 43px; border: 1px solid #b3c99e55; background: #c7d6af14; color: #dce3b5; border-radius: 13px; }.welcome-brand small { display: block; font-size: 10px; color: #a1b6aa; font-weight: 400; margin-top: 2px; letter-spacing: 2px; }
.motion-button { display: inline-flex; align-items: center; gap: 7px; background: #ffffff05; border: 1px solid #a5bfa333; color: #bed0c2; border-radius: 25px; padding: 9px 13px; font-size: 11px; }.motion-button:hover { background: #ffffff10; border-color: #a5bfa366; }
.welcome-main { position: relative; text-align: center; max-width: 1100px; margin: 58px auto 0; }
.welcome-kicker { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; letter-spacing: 2px; color: #bacdb8; }.welcome-kicker > span { width: 5px; height: 5px; background: #d8dca4; border-radius: 50%; box-shadow: 0 0 0 5px #cbd9ac0d; }
h1 { color: #f5f5e9; margin: 24px 0 22px; font-size: clamp(36px, 4.6vw, 62px); line-height: 1.3; font-weight: 600; letter-spacing: -2px; }.assistant-word { position: relative; color: #dfd8a4; }.assistant-word svg { position: absolute; width: 100%; height: 12px; bottom: -8px; left: 0; fill: none; stroke: #c8bf82; stroke-width: 3; stroke-linecap: round; }
.welcome-description { font-size: 14px; line-height: 1.9; color: #b3c7bb; margin: 0 0 25px; }.unlock-button { min-height: 52px; padding: 0 26px; display: inline-flex; align-items: center; gap: 24px; color: #21382c; background: #e3dfb6; border: 1px solid #f4edc6; border-radius: 10px; font-size: 14px; font-weight: 650; box-shadow: 0 8px 30px #00000015; transition: transform .2s, background .2s; }.unlock-button:hover { background: #f2ecc8; transform: translateY(-2px); }.unlock-button:focus-visible { outline: 3px solid #91bba0; outline-offset: 5px; }.welcome-note { color: #93ad9d; font-size: 11px; margin: 13px 0 0; }
.welcome-showcase { width: 530px; max-width: 100%; margin: 25px auto 8px; }
.welcome-footer { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; border-top: 1px solid #bed0b41f; padding-top: 23px; max-width: 980px; margin: 0 auto; }.welcome-footer > div { display: grid; grid-template-columns: 26px 1fr; column-gap: 10px; align-items: center; }.welcome-footer > div > span { grid-row: span 2; font-size: 11px; color: #c5cb9e; align-self: start; padding-top: 3px; }.welcome-footer strong { font-size: 13px; font-weight: 500; color: #dce6d7; }.welcome-footer small { font-size: 11px; color: #8fa99b; margin-top: 7px; }.welcome-caption { text-align: center; color: #829e90; font-size: 10px; margin: 25px 0 0; }
.welcome-notice { max-width:580px; margin:18px auto 0; padding:10px 15px; border:1px solid #bdcfb63d; border-radius:8px; font-size:12px; line-height:1.7; color:#d3dfce; background:#ffffff06; overflow-wrap:anywhere; }
.motion-paused *, .motion-paused *::before { animation-play-state: paused !important; }
@keyframes drift { 0%, 100% { transform: translate3d(0,0,0); } 50% { transform: translate3d(-35px,25px,0); } }
@media (min-width: 1150px) and (min-height: 780px) { .welcome-main { margin-top: 45px; }.welcome-showcase { margin-top: 32px; }.welcome-footer { margin-top: 26px; } }
@media (max-width: 650px) { .welcome-page { padding: 22px 20px; }.welcome-brand { font-size: 21px; }.welcome-main { margin-top: 45px; }.welcome-kicker { font-size: 10px; letter-spacing: 1px; }h1 { font-size: clamp(29px, 7.7vw, 42px); letter-spacing: -1px; margin-top: 23px; }.welcome-description { font-size: 12px; }.welcome-footer { grid-template-columns: 1fr; gap: 19px; max-width: 340px; padding-top: 22px; margin-top: 20px; }.welcome-footer > div { grid-template-columns: 26px 75px 1fr; }.welcome-footer > div > span { grid-row: auto; }.welcome-footer small { margin-top: 0; line-height: 1.6; }.welcome-caption { line-height: 1.8; }.welcome-showcase { margin-top: 30px; }.motion-button { padding: 8px 9px; font-size: 10px; } }
@media (prefers-reduced-motion: reduce) { *, *::before { animation: none !important; transition: none !important; } }
</style>
