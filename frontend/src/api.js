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
    const detail = body && typeof body.detail === 'string' ? body.detail : ''
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
