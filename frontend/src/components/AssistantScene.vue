<script setup>
import AppIcon from './AppIcon.vue'
defineProps({ paused: Boolean, compact: Boolean })
</script>

<template>
  <div class="assistant-scene" :class="{ paused, compact }" aria-label="产品流程示意：客户对话整理为需求，再形成跟进待办">
    <div class="scene-orbit orbit-one" aria-hidden="true"></div>
    <div class="scene-orbit orbit-two" aria-hidden="true"></div>
    <div class="scene-track" aria-hidden="true"><span></span></div>
    <article class="scene-card conversation-card">
      <div class="scene-card-heading"><span class="scene-icon"><AppIcon name="message" :size="16" /></span><span>一段客户对话</span><span class="demo-label">示意</span></div>
      <p class="chat-bubble client">这批礼盒，下周五之前能到吗？</p>
      <p class="chat-bubble seller">收到，我来确认数量和交期。</p>
      <div class="message-typing" aria-hidden="true"><i></i><i></i><i></i></div>
    </article>
    <div class="assistant-core" aria-hidden="true"><span class="core-ring"></span><AppIcon name="spark" :size="30" /></div>
    <article class="scene-card insight-card">
      <div class="scene-card-heading"><span class="scene-icon"><AppIcon name="file" :size="16" /></span><span>需求有了条理</span></div>
      <p class="insight-title">礼盒采购 · 交期确认</p>
      <div class="insight-line"><span>客户关注</span><strong>下周五前送达</strong></div>
      <div class="insight-line"><span>待确认</span><strong>采购数量 / 收货地址</strong></div>
      <div class="insight-foot"><span></span>从沟通中整理，关键信息不遗漏</div>
    </article>
    <article class="scene-card followup-card">
      <div class="scene-card-heading"><span class="scene-icon"><AppIcon name="calendar" :size="16" /></span><span>下一步，也清楚</span></div>
      <p><span class="task-check"><AppIcon name="check" :size="12" /></span>确认备货与物流时间</p>
      <p><span class="task-check pending"></span>整理回复，继续跟进客户</p>
    </article>
  </div>
</template>

<style scoped>
.assistant-scene { position: relative; width: 100%; height: 370px; isolation: isolate; color: #173c34; }
.scene-orbit { position: absolute; border: 1px solid #b3d5bc20; border-radius: 50%; pointer-events: none; }
.orbit-one { width: 355px; height: 355px; left: 50%; top: 9px; transform: translateX(-50%); }
.orbit-two { width: 235px; height: 235px; left: 50%; top: 68px; transform: translateX(-50%); border-style: dashed; }
.scene-track { position: absolute; left: 20%; right: 18%; top: 174px; height: 1px; background: linear-gradient(90deg, transparent, #c4d7a568, transparent); transform: rotate(-15deg); }
.scene-track span { position: absolute; height: 5px; width: 26px; top: -2px; background: #e1d3a2; border-radius: 10px; animation: travel 7s ease-in-out infinite; }
.scene-card { position: absolute; border: 1px solid #eff5e3b0; background: #fafbf4; border-radius: 16px; box-shadow: 0 16px 45px #061b2426; padding: 18px; animation: float 8s ease-in-out infinite; }
.conversation-card { width: 255px; top: 23px; left: 2%; transform: rotate(-4deg); --tilt: -4deg; }
.insight-card { width: 255px; top: 113px; right: 1%; transform: rotate(3deg); --tilt: 3deg; animation-delay: -3s; }
.followup-card { width: 245px; bottom: 0; left: 9%; transform: rotate(-2deg); --tilt: -2deg; animation-delay: -5s; }
.scene-card-heading { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 650; margin-bottom: 13px; }
.scene-icon { display: grid; place-items: center; width: 28px; height: 28px; background: #eaf0df; border-radius: 8px; color: #48674b; }
.demo-label { margin-left: auto; font-size: 10px; color: #6e7c70; font-weight: 400; }
.chat-bubble { font-size: 11px; line-height: 1.65; padding: 9px 10px; margin: 8px 0; max-width: 95%; }
.client { background: #eceee5; border-radius: 2px 10px 10px; }
.seller { margin-left: auto; background: #dce8d1; border-radius: 10px 2px 10px 10px; }
.message-typing { display: flex; gap: 3px; padding-top: 2px; }
.message-typing i { width: 4px; height: 4px; border-radius: 50%; background: #6d8b6e; animation: breathe 3s ease-in-out infinite; }
.message-typing i:nth-child(2) { animation-delay: .25s; }.message-typing i:nth-child(3) { animation-delay: .5s; }
.assistant-core { position: absolute; left: 48%; top: 56px; height: 62px; width: 62px; color: #dfd5ad; background: #345a49; display: grid; place-items: center; border: 1px solid #a9c69c50; border-radius: 20px; transform: rotate(8deg); box-shadow: 0 10px 35px #102e2b20; }
.core-ring { position: absolute; inset: -8px; border: 1px solid #bed4b12e; border-radius: 25px; animation: breathe 5s ease-in-out infinite; }
.insight-title { margin: 0 0 13px; font-size: 14px; font-weight: 650; }
.insight-line { display: flex; justify-content: space-between; gap: 8px; font-size: 10px; padding: 6px 0; }
.insight-line > span { color: #7c8478; }.insight-line strong { font-weight: 500; }
.insight-foot { border-top: 1px solid #e3e7dc; margin-top: 8px; padding-top: 11px; color: #71806a; font-size: 9px; }
.insight-foot > span { display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: #779c67; margin-right: 5px; }
.followup-card p { display: flex; gap: 9px; align-items: center; margin: 9px 0 0; font-size: 11px; }
.task-check { display: inline-grid; place-items: center; width: 16px; height: 16px; border-radius: 5px; color: #fff; background: #69805b; }.task-check.pending { background: transparent; border: 1px solid #bcc9b2; }
.paused *, .paused *::before { animation-play-state: paused !important; }
@keyframes float { 0%, 100% { transform: translateY(0) rotate(var(--tilt, 0deg)); } 50% { transform: translateY(-8px) rotate(var(--tilt, 0deg)); } }
@keyframes breathe { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }
@keyframes travel { 0% { transform: translateX(0); opacity: 0; } 20% { opacity: 1; } 80% { opacity: 1; } 100% { transform: translateX(260px); opacity: 0; } }
@media (max-width: 650px) { .assistant-scene { height: 335px; max-width: 430px; margin: 0 auto; }.scene-card { padding: 13px; }.conversation-card { width: 220px; left: 0; }.insight-card { width: 220px; top: 111px; right: 0; }.followup-card { width: 220px; left: 2%; }.assistant-core { left: auto; right: 12%; top: 23px; width: 48px; height: 48px; }.orbit-one { width: 280px; height: 280px; }.orbit-two { width: 180px; height: 180px; }.scene-track { display: none; } }
@media (max-width: 370px) { .assistant-scene { height: 350px; }.conversation-card { width: 210px; }.insight-card { width: 210px; top: 125px; }.followup-card { width: 210px; }.assistant-core { right: 1%; top: 52px; }.scene-orbit { display: none; } }
@media (max-width: 650px) {
  .assistant-scene { height:auto; display:flex; flex-direction:column; align-items:center; gap:16px; padding:12px 6px; }
  .scene-card { position:relative; inset:auto; width:100%; max-width:300px; --tilt:0deg; transform:none; }
  .assistant-core { position:relative; inset:auto; width:42px; height:42px; order:0; margin:0 0 2px; }
  .conversation-card { order:-1; }.insight-card { order:1; }.followup-card { order:2; }
  .scene-orbit,.scene-track { display:none; }
}
@media (prefers-reduced-motion: reduce) { *, *::before { animation: none !important; } }
</style>
