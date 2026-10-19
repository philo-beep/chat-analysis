<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { getAdminActivity, getAdminOverview } from '../api.js'

const overview = ref(null)
const activity = ref([])
const total = ref(0)
const offset = ref(0)
const limit = 50
const loading = ref(false)
const error = ref('')
let version = 0

function totals(value) {
  return [
    ['账号总数', value.users?.total ?? 0],
    ['有效账号', value.users?.active ?? 0],
    ['需求记录总数', value.records?.total ?? 0],
    ['页面访问次数', value.visits?.total ?? 0],
    ['登录访问用户数', value.visits?.unique_users ?? 0],
  ]
}

async function refresh(nextOffset = 0) {
  if (loading.value) return
  const requestVersion = ++version
  loading.value = true
  error.value = ''
  const responses = await Promise.allSettled([getAdminOverview(7), getAdminActivity(limit, nextOffset)])
  if (requestVersion !== version) return
  const errors = []
  if (responses[0].status === 'fulfilled') overview.value = responses[0].value
  else errors.push(responses[0].reason?.message || '统计读取失败')
  if (responses[1].status === 'fulfilled') {
    activity.value = responses[1].value.items
    total.value = responses[1].value.total
    offset.value = nextOffset
  } else errors.push(responses[1].reason?.message || '访问记录读取失败')
  error.value = [...new Set(errors)].join('；')
  loading.value = false
}

function displayTime(value) {
  if (!value) return '—'
  const date = new Date(typeof value === 'number' ? value * 1000 : value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString()
}

onBeforeUnmount(() => { version += 1 })
refresh()
</script>

<template>
  <section class="card admin-panel" aria-label="网站后台统计">
    <h1>网站后台统计</h1>
    <p>统计从此版本上线后开始采集；访问次数按已登录页面打开或切换计数，不代表独立访客。最近 7 天的功能使用情况如下。</p>
    <button type="button" :disabled="loading" @click="refresh()">{{ loading ? '加载中…' : '刷新统计与访问记录' }}</button>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template v-if="overview">
      <p v-if="overview.note">{{ overview.note }}</p>
      <dl class="totals">
        <div v-for="[label, value] in totals(overview)" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div>
      </dl>
      <h2>功能使用</h2>
      <div class="table-scroll"><table><thead><tr><th>功能</th><th>总次数</th><th>成功</th><th>失败</th></tr></thead><tbody>
        <tr v-for="feature in overview.features" :key="feature.feature"><td>{{ feature.feature }}</td><td>{{ feature.total }}</td><td>{{ feature.succeeded }}</td><td>{{ feature.failed }}</td></tr>
        <tr v-if="!overview.features?.length"><td colspan="4">暂无使用记录</td></tr>
      </tbody></table></div>
      <h2>每日操作次数</h2>
      <p v-if="!overview.daily?.length">暂无记录</p>
      <ul><li v-for="day in overview.daily" :key="day.date">{{ day.date }}：访问 {{ day.visits }} 次，操作 {{ day.actions }} 次</li></ul>
    </template>
    <h2>最近访问与操作记录</h2>
    <p>只显示账号、功能、接口、状态和耗时，不展示密码或聊天内容。</p>
    <div class="table-scroll"><table><thead><tr><th>时间</th><th>账号</th><th>功能</th><th>请求</th><th>状态</th><th>结果</th><th>耗时（毫秒）</th></tr></thead><tbody>
      <tr v-for="item in activity" :key="item.id"><td>{{ displayTime(item.created_at) }}</td><td>{{ item.username || '匿名' }}</td><td>{{ item.feature }}</td><td>{{ item.method }} {{ item.path }}</td><td>{{ item.status_code }}</td><td>{{ item.success ? '成功' : '失败' }}</td><td>{{ item.duration_ms }}</td></tr>
      <tr v-if="!activity.length"><td colspan="7">暂无访问记录</td></tr>
    </tbody></table></div>
    <p>共 {{ total }} 条，当前 {{ total ? offset + 1 : 0 }}–{{ Math.min(offset + limit, total) }} 条</p>
    <div class="paging"><button type="button" :disabled="loading || offset === 0" @click="refresh(Math.max(0, offset - limit))">上一页</button><button type="button" :disabled="loading || offset + limit >= total" @click="refresh(offset + limit)">下一页</button></div>
  </section>
</template>

<style scoped>
.admin-panel { padding: 28px; }
h1 { font-size: 23px; margin: 0 0 12px; color: var(--ink); }
h2 { font-size: 16px; margin: 28px 0 14px; color: var(--ink); }
p { line-height: 1.8; font-size: 12px; color: #626f58; }
.totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 12px; margin: 24px 0; }
.totals > div { padding: 18px; background: #f6f8ef; border: 1px solid var(--line); border-radius: 12px; }
dt { color: #626f58; font-size: 12px; }
dd { font-size: 28px; font-weight: 600; color: var(--brand); margin: 10px 0 0; }
.table-scroll { overflow: auto; border: 1px solid var(--line); border-radius: 10px; }
table { width: 100%; border-collapse: collapse; text-align: left; font-size: 12px; }
th, td { padding: 13px 14px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { background: #f4f6ed; color: #526247; font-size: 11px; font-weight: 600; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: #fafbf7; }
ul { padding-left: 20px; font-size: 12px; line-height: 2; color: #626f58; }
.paging { display: flex; gap: 10px; }
.error { color: #a5372d; }
@media (max-width: 760px) { .admin-panel { padding: 18px; } .totals { grid-template-columns: repeat(2, minmax(0, 1fr)); } .totals > div { padding: 14px; } }
</style>
