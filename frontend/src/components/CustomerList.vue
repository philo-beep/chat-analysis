<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { listCustomers } from '../api.js'
import { currentUser, sessionVersion } from '../auth.js'
import AppIcon from './AppIcon.vue'

defineEmits(['select'])
const query = ref('')
const appliedQuery = ref('')
const items = ref([])
const total = ref(0)
const offset = ref(0)
const limit = 24
const loading = ref(false)
const error = ref('')
let epoch = 0
onBeforeUnmount(() => { epoch++ })

function formatTime(value) {
  if (!value) return '尚无整理时间'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间待确认' : date.toLocaleString('zh-CN', { hour12: false })
}

async function load(nextOffset = 0, search = false) {
  const requestEpoch = ++epoch
  const version = sessionVersion.value
  if (search) appliedQuery.value = query.value.trim()
  const active = () => requestEpoch === epoch && currentUser.value && version === sessionVersion.value
  loading.value = true
  error.value = ''
  items.value = []
  try {
    const response = await listCustomers({ q: appliedQuery.value, limit, offset: nextOffset })
    if (!active()) return
    items.value = response.items
    total.value = response.total
    offset.value = nextOffset
  } catch (e) {
    if (active()) error.value = `暂时没能读到客户资料：${e.message}`
  } finally {
    if (active()) loading.value = false
  }
}
onMounted(() => load())
</script>

<template>
  <section class="customers-page" aria-label="我的客户">
    <header class="page-heading"><div><h1>我的客户</h1><p>把聊过的客户记下来，让下一次沟通更有准备。</p></div><button :disabled="loading" @click="load(offset)"><AppIcon name="refresh" :size="15" />刷新</button></header>
    <form class="search-form" role="search" @submit.prevent="load(0, true)">
      <label for="customer-search">找客户</label>
      <input id="customer-search" v-model="query" type="search" maxlength="200" placeholder="输入客户名字或公司" />
      <button class="primary" :disabled="loading" type="submit">搜索</button>
      <button v-if="appliedQuery" :disabled="loading" type="button" @click="query = ''; load(0, true)">查看全部</button>
    </form>
    <p v-if="loading" class="empty" role="status">正在整理客户资料…</p>
    <div v-else-if="error" class="error" role="alert">{{ error }} <button @click="load(offset)">重试</button></div>
    <template v-else>
      <p v-if="!items.length" class="empty">{{ appliedQuery ? '还没找到这个名字或公司，换个关键词试试。' : '把和客户的聊天整理一次，这里就会留下客户资料。' }}</p>
      <div v-else class="customer-grid">
        <button v-for="customer in items" :key="customer.id" type="button" class="customer-card card" :aria-label="`查看客户：${customer.display_name || '未知'}`" @click="$emit('select', customer.id)">
          <div class="card-heading"><span class="customer-avatar"><AppIcon name="customers" :size="22" /></span><h2>{{ customer.display_name || '未知' }}</h2><AppIcon name="arrow" :size="16" /></div>
          <p class="company">{{ customer.company || '公司待了解' }}</p>
          <p class="role">{{ customer.role || '角色待了解' }}</p>
          <p v-if="customer.next_follow_up && customer.next_follow_up !== '未知'" class="next-step">下一步：{{ customer.next_follow_up }}</p>
          <small>最近整理：{{ formatTime(customer.last_analyzed_at || customer.updated_at) }}</small>
        </button>
      </div>
      <div v-if="total > limit" class="pagination"><button :disabled="offset === 0" @click="load(Math.max(0, offset - limit))">上一页</button><span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} / {{ total }} 位客户</span><button :disabled="offset + limit >= total" @click="load(offset + limit)">下一页</button></div>
    </template>
  </section>
</template>

<style scoped>
.customers-page { max-width: 1160px; margin: auto; }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
h1 { color: var(--ink); font-size: 26px; margin-bottom: 8px; }
.page-heading p, small, .role { color: var(--muted); font-size: 13px; line-height: 1.7; }
.search-form { display: flex; align-items: center; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
.search-form label { font-size: 13px; }
.search-form input { flex: 1; min-width: 150px; }
.customer-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); gap: 16px; }
.customer-card { display: flex; flex-direction: column; align-items: stretch; text-align: left; padding: 20px; min-width: 0; overflow-wrap: anywhere; }
.card-heading { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
.card-heading h2 { color: var(--ink); font-size: 18px; margin: 0; flex: 1; }
.customer-avatar { background: var(--soft); color: var(--brand); border-radius: 12px; padding: 8px; }
.company { font-weight: 600; margin-bottom: 6px; }
.role { margin-bottom: 12px; }
.next-step { border-top: 1px solid var(--line); padding-top: 12px; font-size: 13px; line-height: 1.7; }
small { font-size: 11px; margin-top: auto; padding-top: 8px; }
.empty { text-align: center; color: var(--muted); padding: 50px 18px; line-height: 1.8; }
.pagination { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 24px; font-size: 12px; }
@media(max-width: 480px) { .page-heading { gap: 8px; } h1 { font-size: 22px; } .search-form label { width: 100%; } }
</style>
