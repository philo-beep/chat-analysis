// 前端请求封装，A 负责
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
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`请求失败：${res.status} ${res.statusText}`)
  }
  return res.json()
}

// 输入聊天原文，返回约定的分析结果。
export function analyze(text) {
  return request('/analyze', {
    method: 'POST',
    body: JSON.stringify({ text }),
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
