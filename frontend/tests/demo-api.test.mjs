import assert from 'node:assert/strict'
import test from 'node:test'
import { analyze } from '../src/api.js'

test('固定文字演示显式携带标记，普通及旧调用不带演示标记', async () => {
  const original = globalThis.fetch
  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({ url, ...options })
    return new Response(JSON.stringify({ id: 1, is_sample: true }), {
      headers: { 'Content-Type': 'application/json' },
    })
  }
  try {
    await analyze({ text: '演示原文', demo: true })
    await analyze({ text: '用户改过的原文', demo: false })
    await analyze('旧调用原文')
    assert.equal(requests[0].headers.get('X-Keyoushu-Demo'), '1')
    assert.equal(requests[1].headers.has('X-Keyoushu-Demo'), false)
    assert.equal(requests[2].headers.has('X-Keyoushu-Demo'), false)
    assert.deepEqual(JSON.parse(requests[0].body), { text: '演示原文' })
  } finally { globalThis.fetch = original }
})

test('截图演示保留原文件与文字并显式携带标记', async () => {
  const original = globalThis.fetch
  let submitted
  globalThis.fetch = async (_url, options) => {
    submitted = options
    return new Response('{}', { headers: { 'Content-Type': 'application/json' } })
  }
  try {
    const image = new Blob(['synthetic image bytes'], { type: 'image/png' })
    await analyze({ text: '客户名称：演示客户\n', image, demo: true })
    assert.equal(submitted.headers.get('X-Keyoushu-Demo'), '1')
    assert.equal(submitted.headers.has('Content-Type'), false)
    assert.equal(submitted.body.get('text'), '客户名称：演示客户\n')
    assert.equal(await submitted.body.get('image').text(), 'synthetic image bytes')
  } finally { globalThis.fetch = original }
})
