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

const demoText = `甲方（客户/需求方）：我们准备举办一次团队活动，想定制100件文化衫，总预算3000元。先沟通需求和可行方案，暂时不要安排生产。
乙方（商家/执行方）：收到，我负责方案、报价和生产协调，您负责内部需求与审批。我们先把穿着场景、面料、图案和交付要求逐项说明，确认后再排计划。
甲方（客户/需求方）：主要是白天户外活动，结束后还要拍团队合照。我们希望穿着舒适，图案不要太花，之后日常也能穿。
乙方（商家/执行方）：户外活动可以比较纯棉和速干两种面料。我会整理手感、透气性和印制效果的对比，不会把推荐方案直接当作您已确认的要求。
甲方（客户/需求方）：面料确定选纯棉。颜色先考虑白色和深蓝色，希望整体简洁，胸前放活动标识，背面只放一句通用口号。
乙方（商家/执行方）：可以，颜色会影响标识的呈现。我先做白底和深蓝底两版效果图，实物颜色以布样核对，屏幕图片只能作为参考。
甲方（客户/需求方）：这里有个问题，内部新增了一批参与人员。数量改成150件，原来的采购规模不再适用，费用也需要重新核算。
乙方（商家/执行方）：已记录数量变更。我会按最终数量重新计算面料、印制和包装费用，并把费用拆开列，避免总价里混入未经确认的项目。
甲方（客户/需求方）：总预算最终确认为6000元。这是内部审批上限，不代表直接接受任何报价；如果方案超出上限，请先给我们可选的调整办法。
乙方（商家/执行方）：明白。我负责在2026年11月3日17:00前提交分项报价和两版效果图，前提是先收到可用于排版的标识文件，不擅自承诺最终成交价格。
甲方（客户/需求方）：我们需要你们提供设计。甲方负责提供标识、口号和使用规范，乙方负责版式设计；不要把我们提供素材理解为已经有完整设计稿。
乙方（商家/执行方）：分工清楚了。请甲方在2026年11月2日12:00前提供标识矢量文件、口号文字和使用规范；如果文件缺失，我会先列出问题，设计节点需一起重新确认。
甲方（客户/需求方）：素材由甲方项目对接人统一收集，我会安排提交。标识只能等比例使用，不增加其他品牌元素，口号需要内部审阅后才算定稿。
乙方（商家/执行方）：收到。我会把素材完整性检查列为首个任务，检查通过再开始排版；口号未定稿时，效果图会明确标为待确认，不直接交给车间。
甲方（客户/需求方）：我们担心白色不耐脏，但深蓝色会让标识显得不够清楚。先保留两版对比，不要只因为制作方便就替我们决定颜色。
乙方（商家/执行方）：这个分歧可以通过同版式配色对比解决。我在效果图中展示标识对比度，并提供可选布样；甲方在2026年11月4日15:00前集中反馈，尽量避免多人分别改稿。
甲方（客户/需求方）：同意集中反馈，甲方项目对接人汇总意见后统一回复。颜色仍待确认，最终需要看到效果图和布样后决定，现阶段不作为已确认事实。
乙方（商家/执行方）：我会把颜色列入待确认清单。设计评审由甲方项目对接人负责组织，乙方负责解释工艺限制，双方书面确认后才锁定图案和配色。
甲方（客户/需求方）：尺码名单现在还不完整，部分人员尚未反馈。我们不接受按平均比例直接分配，甲方负责收集个人尺码，乙方提供尺码表和测量说明。
乙方（商家/执行方）：我在2026年11月2日18:00前发尺码表，甲方在2026年11月5日18:00前回传汇总名单。名单没有确认前，不裁剪大货，缺少的部分会单独提醒。
甲方（客户/需求方）：包装希望每件独立装袋，并在袋外标注尺码，方便现场分发。名单只提供尺码汇总，不需要收集真实姓名或其他个人资料。
乙方（商家/执行方）：可以作为包装方案评估。我会在报价中单列独立装袋和尺码标签费用，并提交包装示意，是否采用由甲方在报价确认时一起决定。
甲方（客户/需求方）：还有一个分歧，内部有人希望先看实物再批量制作，也有人担心打样拖慢进度。我们决定先评审样衣，通过之后再启动批量生产。
乙方（商家/执行方）：我负责在2026年11月9日17:00前提供样衣评审材料，依赖图案、颜色和尺码方案提前锁定；甲方负责在2026年11月10日17:00前汇总评审结论。
甲方（客户/需求方）：样衣评审需要检查面料手感、标识位置、印色和缝线。发现问题先修改并复核，不能为了赶进度默认甲方已经接受。
乙方（商家/执行方）：我会用检查表记录每项结论，修改项要附前后对比。未通过项由乙方处理，甲方书面确认样衣后，我再申请生产排期。
甲方（客户/需求方）：收货时间最终确认为2026年11月20日前收到，活动安排不能后移。但这只是甲方的交付要求，仍需要乙方核实生产和物流是否可行。
乙方（商家/执行方）：我会在2026年11月4日18:00前反馈生产与物流可行性，并给出预计发货窗口。样衣确认、付款条件或地址信息延迟时，需及时重新评估，不能直接保证如期到货。
甲方（客户/需求方）：收货城市已确定，但具体仓库地址和签收联系人还要内部确认。甲方负责补齐，乙方在资料齐全前先不要制作运单。
乙方（商家/执行方）：请甲方在2026年11月12日12:00前提供完整地址和签收方式。我负责核对物流覆盖范围，确认后再提供运输方案及预计到达时间。
甲方（客户/需求方）：付款比例和开票要求尚未审批，请列为待确认事项。甲方采购对接人负责内部沟通，未确认之前不要假设已经支付定金，也不要据此启动生产。
乙方（商家/执行方）：我负责提交付款条件和开票资料清单，甲方采购对接人在2026年11月6日17:00前反馈。生产启动以样衣、订单和双方约定的付款条件全部确认作为前置条件。
甲方（客户/需求方）：如果后面有人临时增加需求，请单独记录变更，不要口头答应后直接做。涉及数量、费用或交期变化，都要甲方采购对接人书面批准。
乙方（商家/执行方）：同意。我负责维护变更记录，标明提出事项、费用与排期影响，收到甲方批准后才更新执行计划；未批准的内容保持待确认状态。
甲方（客户/需求方）：质量方面，希望出货前检查尺码、图案位置、明显污损和包装标签。抽检规则及不合格品处理方式还要双方确认，先不要擅自填一个标准。
乙方（商家/执行方）：我负责提供验收检查表和不合格品处理建议，甲方在样衣评审时一并确认。出货前由乙方做检查并发送记录，甲方核对后安排收货。
甲方（客户/需求方）：运输途中如果可能延误，要主动提醒并给出备选方案，不要等活动前才通知。额外运输费用需先走甲方审批，不能事后直接加到账单。
乙方（商家/执行方）：我负责跟踪物流，预计偏离计划时立即说明原因、影响和备选方案。未经甲方书面同意，不自行选择会增加费用的运输方式。
甲方（客户/需求方）：跟进方式采用一个统一清单，区分已确认需求、待确认问题和建议行动。每项行动注明负责人、截止节点和前置条件，不要把建议写成客户已经接受的承诺。
乙方（商家/执行方）：我负责维护清单和版本，甲方项目对接人负责核对需求与内部反馈。每次评审结束双方更新状态，未完成的依赖要写明对后续节点的影响。
甲方（客户/需求方）：目前可以确认的是采购规模、预算上限、面料、设计分工和收货要求。颜色、尺码分布、包装采用方式、付款条件及验收细则仍需要按流程确认。
乙方（商家/执行方）：我会据此准备设计方案、核算分项报价并核实生产物流时间，同时保留待确认事项，不把尚未审批的方案当成正式订单。
甲方（客户/需求方）：甲方这边由项目对接人负责素材、尺码和反馈汇总，采购对接人负责报价、付款和变更审批；乙方负责设计、打样、生产协调与物流跟踪。
乙方（商家/执行方）：收到。我会把双方分工写进会后清单，先完成资料检查和尺码表发送；凡是等待甲方资料或审批的任务，都标明依赖，不提前宣称已完成。
甲方（客户/需求方）：请先发本次沟通纪要和待办清单给我们核对。我们按清单推进，遇到遗漏再补充，正式确认之前暂不下达生产指令。
乙方（商家/执行方）：好的，我会整理已确认事项、双方待办、截止节点、依赖和待确认问题供您核对；下一步先落实素材、设计报价和生产物流可行性，再依次推进评审与执行。`

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
    <footer class="input-footer"><AppIcon name="shield" :size="13" /><span>保留聊天原文，分析有据可查</span><span class="shortcut">Ctrl/Cmd + Shift + D 填充演示样例</span></footer>
  </section>
</template>

<style scoped>
.chat-input { overflow: hidden; }
.input-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 21px 26px; border-bottom: 1px solid var(--line); }
.input-heading h2 { margin: 0 0 4px; font-size: 16px; color: var(--ink); font-weight: 600; }
.input-heading p { margin: 0; color: var(--muted); font-size: 11px; }
.demo-button { border-color: transparent; color: var(--brand); font-size: 12px; padding: 6px 0 6px 10px; white-space: nowrap; }
.input-body { padding: 22px 26px; }
.customer-label { display: block; margin: 19px 0 8px; font-size: 12px; font-weight: 600; color: #4e5a45; }
.customer-label:first-child { margin-top: 0; }
.customer-name { max-width: 440px; }
.role-hint { margin: 0 0 10px; color: #626f58; font-size: 11px; line-height: 1.8; }
textarea { min-height: 160px; background: #fdfdf9; line-height: 1.9; }
.upload-row { margin-top: 12px; display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.upload-button { display: inline-flex; align-items: center; border: 1px dashed #b9c3ad; border-radius: 7px; padding: 8px 13px; color: #526544; background: #fafbf7; font-size: 12px; position: relative; cursor: pointer; overflow: hidden; }
.upload-button:hover { border-color: var(--brand); }
.upload-button input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.file-name { max-width: 100%; overflow-wrap: anywhere; font-size: 11px; background: var(--soft); border: 0; }
.upload-row .hint { font-size: 10px; }
.preview { display: block; max-width: min(100%, 420px); max-height: 240px; margin-top: 14px; border: 1px solid var(--line); border-radius: 8px; }
.actions { border-top: 1px solid var(--line); padding-top: 19px; margin-top: 21px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.actions .primary { min-width: 136px; min-height: 42px; }
.actions .ghost { border-color: transparent; color: #626f58; }
.input-meta { color: #626f58; font-size: 11px; margin-left: auto; }
.input-footer { display: flex; align-items: center; gap: 6px; padding: 12px 26px; background: #fafbf7; border-top: 1px solid var(--line); color: #626f58; font-size: 10px; }
.shortcut { margin-left: auto; }
.loading-note { color: var(--brand); font-size: 12px; margin: 12px 0 0; line-height: 1.6; }
.spinner { width: 14px; height: 14px; border: 2px solid #ffffff66; border-top-color: #fff; border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) { .input-heading { padding: 18px; flex-wrap: wrap; } .input-body { padding: 18px; } .input-heading p { font-size: 10px; } .demo-button { padding: 0; min-height: 24px; margin-left: 46px; } .input-meta { flex-basis: 100%; margin: 0; } .input-footer { padding: 12px 18px; flex-wrap: wrap; } .shortcut { display: none; } }
</style>
