// 分类只是已保存记录的只读视图，不推断完成状态或问题是否已经解决。
export function buildRecordViews(records) {
  const views = { tasks: [], questions: [], screenshots: [] }
  for (const record of records) {
    const source = {
      recordId: record.id,
      title: record.title || '未命名',
      createdAt: record.created_at,
      isSample: record.result?.is_sample === true,
    }
    const result = record.result || {}
    for (const kind of ['tasks', 'suggested_tasks', 'ddl_tasks', 'questions']) {
      const values = result[kind]
      if (!Array.isArray(values)) continue
      values.forEach((value, index) => {
        const text = typeof value === 'string' ? value : kind === 'questions' ? value?.question : value?.title
        if (typeof text !== 'string' || !text.trim()) return
        const detail = typeof value === 'object' ? value : {}
        const state = kind === 'tasks' ? result.action_states?.[String(index)] : detail
        views[kind === 'questions' ? 'questions' : 'tasks'].push({
          ...source, key: `${record.id}:${kind}:${index}`, text, taskIndex: index,
          kind, status: state?.status, reason: detail.reason, priority: detail.priority,
          dueDate: detail.ddl_date, initialGuess: detail.initial_guess, confirmedAnswer: detail.confirmed_answer,
          expanded: result.analysis_version === 2 || Array.isArray(result.ddl_tasks) || Array.isArray(result.suggested_tasks),
        })
      })
    }
    if (typeof record.source_image === 'string' && record.source_image.trim()) {
      views.screenshots.push({
        ...source, key: `${record.id}:screenshot`, image: record.source_image,
        text: record.source_transcript
          ? record.source_transcript.slice(0, 240) + (record.source_transcript.length > 240 ? '…（完整转录请打开来源记录）' : '')
          : '暂无截图转录，可打开来源记录核对原图。',
      })
    }
  }
  return views
}

// 列表接口仅含摘要；详情最多 3 个并发，按服务端更新时间复用本次会话缓存。
// isCurrent 同时检查账号版本和加载批次，防止迟到响应写入新账号。
export async function loadRecordDetails(summaries, fetchRecord, {
  cache = new Map(), isCurrent = () => true, onProgress = () => {}, concurrency = 3,
} = {}) {
  const details = new Array(summaries.length)
  const failures = []
  let cursor = 0
  let completed = 0
  async function worker() {
    while (isCurrent()) {
      const index = cursor++
      if (index >= summaries.length) return
      const summary = summaries[index]
      try {
        const cached = cache.get(summary.id)
        const record = cached && cached.updatedAt === summary.updated_at
          ? cached.record : await fetchRecord(summary.id)
        if (!isCurrent()) return
        if (!record || !record.result || typeof record.result !== 'object') {
          throw new Error('记录详情不完整')
        }
        cache.set(summary.id, { updatedAt: summary.updated_at, record })
        details[index] = record
      } catch (error) {
        if (!isCurrent()) return
        failures.push({ id: summary.id, message: error instanceof Error ? error.message : '读取失败' })
      }
      if (isCurrent()) onProgress(++completed)
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, summaries.length) }, worker))
  return { records: details.filter(Boolean), failures }
}
