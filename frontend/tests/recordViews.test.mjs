import assert from 'node:assert/strict'
import test from 'node:test'
import { buildRecordViews, loadRecordDetails } from '../src/recordViews.js'
import { hashForSection, routeFromHash, sectionFromHash } from '../src/navigation.js'

const summary = (id, updated_at = 'v1') => ({ id, updated_at })
const detail = (id) => ({ id, result: { tasks: [`任务 ${id}`], questions: [] } })

test('扩展记录目录合并普通/推进/日期任务，问题保留确认答案与来源', () => {
  const views = buildRecordViews([{ id: 9, title: '客户沟通', result: {
    analysis_version: 2, tasks: ['普通建议'], action_states: { 0: { status: 'accepted' } },
    suggested_tasks: [{ title: '对比方案', reason: '客户在比较竞品', priority: 'high', status: 'ignored' }],
    ddl_tasks: [{ title: '提交方案', ddl_date: '2026-10-30', status: 'added' }],
    questions: [{ question: '确认日期？', initial_guess: '下周五', confirmed_answer: '10月30日' }],
  } }])
  assert.deepEqual(views.tasks.map(item => item.kind), ['tasks', 'suggested_tasks', 'ddl_tasks'])
  assert.deepEqual(views.tasks.map(item => item.status), ['accepted', 'ignored', 'added'])
  assert.equal(views.tasks[1].priority, 'high')
  assert.equal(views.tasks[2].dueDate, '2026-10-30')
  assert.equal(views.questions[0].confirmedAnswer, '10月30日')
  assert.equal(views.questions[0].recordId, 9)
})

test('分类保留来源和重复内容，不把空白、缺失来源或普通文本误认为截图', () => {
  const views = buildRecordViews([
    { ...detail(2), title: '需求单', result: { tasks: ['任务', ' ', '任务'], questions: ['确认颜色'], is_sample: true }, source_image: 'data:image/png;base64,test', source_transcript: '转录'.repeat(300) },
    { id: 1, result: { tasks: [], questions: [] }, source_input: { text: '普通聊天' } },
  ])
  assert.equal(views.tasks.length, 2)
  assert.notEqual(views.tasks[0].key, views.tasks[1].key)
  assert.equal(views.tasks[0].recordId, 2)
  assert.equal(views.questions.length, 1)
  assert.equal(views.screenshots.length, 1)
  assert.equal(views.tasks[0].isSample, true)
  assert.match(views.screenshots[0].text, /完整转录请打开来源记录/)
})

test('并发最多 3 个，完成顺序不改变来源顺序，缓存按更新时间失效', async () => {
  let inflight = 0, peak = 0, calls = 0
  const cache = new Map()
  const fetchRecord = async (id) => {
    calls++; inflight++; peak = Math.max(peak, inflight)
    await new Promise((resolve) => setTimeout(resolve, (7 - id) * 2))
    inflight--
    return detail(id)
  }
  const summaries = [1, 2, 3, 4, 5, 6].map((id) => summary(id))
  const loaded = await loadRecordDetails(summaries, fetchRecord, { cache })
  assert.equal(peak, 3)
  assert.deepEqual(loaded.records.map((item) => item.id), [1, 2, 3, 4, 5, 6])
  await loadRecordDetails(summaries, fetchRecord, { cache })
  assert.equal(calls, 6)
  await loadRecordDetails([summary(1, 'v2')], fetchRecord, { cache })
  assert.equal(calls, 7)
})

test('单条读取失败保留其他结果，并记录失败来源', async () => {
  const loaded = await loadRecordDetails([summary(1), summary(2)], async (id) => {
    if (id === 1) throw new Error('记录不存在')
    return detail(id)
  })
  assert.deepEqual(loaded.records.map((item) => item.id), [2])
  assert.deepEqual(loaded.failures, [{ id: 1, message: '记录不存在' }])
})

test('账号或批次失效后，迟到详情不得写入缓存、列表或进度', async () => {
  let active = true, release
  const cache = new Map(), progress = []
  const loading = loadRecordDetails([summary(1), summary(2)], () => new Promise((resolve) => { release = resolve }), {
    cache, concurrency: 1, isCurrent: () => active, onProgress: (value) => progress.push(value),
  })
  active = false
  release(detail(1))
  assert.deepEqual((await loading).records, [])
  assert.equal(cache.size, 0)
  assert.deepEqual(progress, [])
})

test('空记录不发起详情请求；hash 刷新可恢复目录且后台仍受权限限制', async () => {
  const loaded = await loadRecordDetails([], () => { throw new Error('不应调用') })
  assert.deepEqual(loaded, { records: [], failures: [] })
  for (const section of ['workspace', 'tasks', 'questions', 'screenshots', 'calendar', 'calendar/gantt']) {
    assert.equal(sectionFromHash(hashForSection(section)), section)
  }
  assert.equal(sectionFromHash('#/admin'), 'workspace')
  assert.equal(sectionFromHash('#/admin', true), 'admin')
  assert.equal(sectionFromHash('#/unknown'), 'workspace')
})

test('单份聊天地址保留记录和分类，非法记录编号不得成为有效上下文', () => {
  for (const section of ['tasks', 'questions', 'screenshots']) {
    const hash = hashForSection(section, 12)
    assert.equal(hash, `#/records/12/${section}`)
    assert.deepEqual(routeFromHash(hash), { section, recordId: 12 })
    assert.equal(sectionFromHash(hash), section)
  }
  for (const hash of ['#/records/0/tasks', '#/records/-1/tasks', '#/records/1.5/tasks', '#/records/9007199254740992/tasks', '#/records/1/admin']) {
    assert.deepEqual(routeFromHash(hash), { section: 'workspace', recordId: null })
  }
  assert.equal(hashForSection('workspace', 12), '#/')
})

test('客户与历史快照地址独立于聊天范围，刷新可恢复且拒绝非法编号', () => {
  assert.deepEqual(routeFromHash(hashForSection('customers')), { section: 'customers', recordId: null, customerId: null, snapshotId: null })
  assert.deepEqual(routeFromHash(hashForSection('customers', null, 8)), { section: 'customers', recordId: null, customerId: 8, snapshotId: null })
  assert.deepEqual(routeFromHash(hashForSection('customers', null, 8, 12)), { section: 'customers', recordId: null, customerId: 8, snapshotId: 12 })
  for (const hash of ['#/customers/0', '#/customers/-1', '#/customers/1/snapshots/0', '#/customers/9007199254740992', '#/customers/1/snapshots/9007199254740992']) {
    assert.deepEqual(routeFromHash(hash), { section: 'workspace', recordId: null })
  }
})
