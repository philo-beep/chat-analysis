// 前端请求封装，A 负责。
// 约定见 docs/api.md：字段名称、数据类型、空值规则都要固定。
import { clearSession, getAuthToken } from './auth.js'

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
  const { anonymous = false, invalidateOn401 = true, ...fetchOptions } = options
  const requestToken = anonymous ? '' : getAuthToken()
  const headers = new Headers(options.headers || {})
  if (requestToken) headers.set('Authorization', `Bearer ${requestToken}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  let res
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...fetchOptions, headers })
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
    if (res.status === 401 && requestToken && invalidateOn401) clearSession(requestToken)
    const detail = typeof body?.detail === 'string' ? body.detail
      : Array.isArray(body?.detail) ? validationMessage(body.detail) : ''
    const error = new Error(body?.message || detail || `请求失败：${res.status} ${res.statusText}`)
    error.status = res.status
    throw error
  }
  if (contentType.includes('application/json')) return body
  return res.text()
}

async function authRequest(path, options) {
  const response = await request(path, options)
  if (response?.code !== 0) throw new Error(response?.message || '服务端响应格式错误')
  return response.data
}

export function login(username, password) {
  return authRequest('/api/auth/login', {
    method: 'POST', anonymous: true, body: JSON.stringify({ username, password }),
  })
}

export function register(username, password) {
  return authRequest('/api/auth/register', {
    method: 'POST', anonymous: true, body: JSON.stringify({ username, password }),
  })
}

export function getCurrentUser() {
  return authRequest('/api/auth/me')
}

export function logout() {
  return authRequest('/api/auth/logout', { method: 'POST' })
}

export function getAdminOverview(days = 7) {
  return authRequest(`/api/admin/overview?days=${days}`)
}

export function getAdminActivity(limit = 50, offset = 0) {
  return authRequest(`/api/admin/events?limit=${limit}&offset=${offset}&days=7`)
}

export function trackPageView() {
  return authRequest('/api/usage/visit', {
    method: 'POST', body: JSON.stringify({}),
  })
}

// 非关键客户端统计失败不能干扰已经完成的复制或当前页面会话。
export function trackCopy(id) {
  return authRequest('/api/usage/copy', {
    method: 'POST', invalidateOn401: false, body: JSON.stringify({ record_id: id }),
  })
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

// 下载同样通过统一请求层携带 token，不将凭据放进 URL。
export function exportRecordData(id) {
  return request(`/records/${id}/export`)
}
