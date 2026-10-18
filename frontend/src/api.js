// 前端请求封装，A 负责。
// 约定见 docs/api.md：字段名称、数据类型、空值规则都要固定。

const BASE_URL = import.meta.env?.VITE_API_BASE ?? 'http://127.0.0.1:8000'

// 开发用示例结果：后端还没接上真实模型时，前端先用它跑通页面。
export const MOCK_RESULT = {
  requirements: [
    {
      field: '数量',
      value: '100 件',
      evidence: '我们想定制 100 件文化衫',
    },
  ],
  questions: ['请确认尺码分布'],
  tasks: ['准备初步设计方案'],
  reply: '收到，请再提供一下尺码分布，方便准备方案。',
}

const fieldNames = {
  text: '聊天原文', image: '聊天截图', result: '分析结果',
  requirements: '需求列表', field: '字段名称', value: '需求内容', evidence: '原文依据',
  questions: '待确认问题', tasks: '建议待办', reply: '回复草稿', is_sample: '来源标记',
  record_id: '记录编号',
}

function validationMessage(detail) {
  return detail.map((item) => {
    if (!item || typeof item !== 'object') return ''
    const location = Array.isArray(item.loc) ? item.loc : []
    const field = location.filter((part) => !['body', 'query', 'path'].includes(part))
      .map((part) => typeof part === 'number' ? `第 ${part + 1} 项` : fieldNames[part] || String(part))
      .join(' > ') || '输入内容'
    const messages = {
      missing: '请补充此项', string_type: '请填写文字', list_type: '应为列表',
      bool_type: '应为是或否', int_type: '应为整数', int_parsing: '应为整数',
      string_too_short: '内容过短，请补充', string_too_long: '内容过长，请缩短',
      string_pattern_mismatch: '格式不正确，请检查', extra_forbidden: '包含不支持的字段',
      json_invalid: '数据格式不正确，请重新提交',
    }
    return `${field}：${messages[item.type] || (typeof item.msg === 'string' ? item.msg : '格式不正确，请检查')}`
  }).filter(Boolean).join('；')
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  let res
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  } catch {
    throw new Error('无法连接后端服务，请确认后端已启动后重试')
  }
  let body = null
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    try {
      body = await res.json()
    } catch {
      body = null
    }
  }
  if (!res.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail
      : Array.isArray(body?.detail) ? validationMessage(body.detail) : ''
    throw new Error(detail || `请求失败：${res.status} ${res.statusText}`)
  }
  if (contentType.includes('application/json')) return body
  return res.text()
}

// 输入聊天原文和可选聊天截图，返回约定的分析结果。
// 兼容旧调用 analyze('...')，截图请求使用 multipart/form-data。
export function analyze(input) {
  const payload = typeof input === 'string' ? { text: input, image: null } : input || {}
  if (payload.image) {
    const form = new FormData()
    form.append('text', payload.text || '')
    form.append('image', payload.image, payload.image.name || 'chat-screenshot')
    return request('/analyze', { method: 'POST', body: form })
  }
  return request('/analyze', {
    method: 'POST',
    body: JSON.stringify({ text: payload.text || '' }),
  })
}

export function listRecords() {
  return request('/records')
}

export function getRecord(id) {
  return request(`/records/${id}`)
}

export function saveRecord(id, result) {
  return request(`/records/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ result }),
  })
}

export function exportRecord(id) {
  return `${BASE_URL}/records/${id}/export`
}
