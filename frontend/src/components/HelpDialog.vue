<script setup>
import CalendarDialog from './CalendarDialog.vue'
defineProps({ topic: { type: String, default: 'calendar' } })
defineEmits(['close'])
const content = {
  calendar: { title: '日历与圆点', text: ['每个圆点代表当天进行中的一件事，区间包含开始日和截止日。开始日使用后端 AI 的 start_date，缺失时使用创建日。', '颜色反映距离今天的截止时间，越接近越醒目；深红描边表示已经逾期。点击圆点查看详情，点击日期空白处创建事件。'], steps: ['选择日期', '新建或打开事件', '查看每日圆点', '完成任务并结束事件'] },
  level: { title: '调整紧迫等级', text: ['自动模式按距离今天的截止天数计算，每两天降低一级。手动选择 1–5 级后，等级固定，不再随时间变化。', '点击“恢复自动”后重新按截止日期计算；逾期事项仍以深红描边优先提醒。'], steps: ['打开事件详情', '选择自动或 1–5 级', '保存并立即更新', '需要时恢复自动'] },
  todo: { title: '无 DDL 待办池', text: ['暂时没有截止日期的事情放在这里，只填写标题就能保存。确定安排后，点击“设 DDL”选择日期，待办会进入日历。', '任务完成后点击“完成任务”，可在已完成列表查到，也可重新打开。'], steps: ['新增待办', '暂存待办池', '点击设 DDL', '保存后进入日历'] },
  gantt: { title: '日历与甘特图切换', text: ['点击切换按钮或按 G，在日历与甘特图间切换。正在输入文字或弹窗打开时，快捷键不会触发。', '横条从开始日延伸到截止日；逾期部分以虚线延伸到今天。可以按日或周查看，勾选“显示已完成”查看已结束事项。'], steps: ['点击切换或按 G', '选择日或周刻度', '查看计划与逾期段', '再次按 G 返回'] },
  event: { title: '创建与结束事件', text: ['在日历日期格点击新增，填写标题与截止日期，开始日由后端提供，不能在这里填写。已有事项可修改截止日期、备注和等级。', '做完后点击“完成任务”，圆点会消失，记录保留在已完成列表；需要继续工作可重新打开。截止日早于开始日时仅显示异常标记，请核对日期。'], steps: ['填写标题和截止日', '保存事件', '执行任务', '完成任务'] },
}
</script>
<template><CalendarDialog :title="content[topic].title" @close="$emit('close')"><p v-for="text in content[topic].text" :key="text" class="explanation">{{ text }}</p><ol class="flow" aria-label="操作流程"><li v-for="(step, i) in content[topic].steps" :key="step"><span>{{ i + 1 }} · {{ step }}</span><b v-if="i < content[topic].steps.length - 1" aria-hidden="true">→</b></li></ol><button class="primary" @click="$emit('close')">知道了</button></CalendarDialog></template>
<style scoped>.explanation{font-size:14px;line-height:1.9}.flow{list-style:none;display:flex;flex-wrap:wrap;gap:8px;padding:0;margin:20px 0}.flow li{display:flex;align-items:center;gap:8px}.flow span{background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:10px;font-size:12px}.flow b{color:#6f7c64}
.explanation { color: #526246; }
.flow { background: var(--canvas); border: 1px solid var(--line); border-radius: 12px; padding: 14px; }
.flow li { min-width: 0; max-width: 100%; }
.flow span { color: var(--ink); overflow-wrap: anywhere; line-height: 1.7; background: var(--surface); border-radius: 8px; }
</style>
