import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { readFile, writeFile, mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const evidence = resolve(root, 'docs/evidence')
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_NODE_MODULES
  ? resolve(process.env.PLAYWRIGHT_NODE_MODULES, 'playwright') : 'playwright')
const python = process.env.PYTHON_EXECUTABLE || 'python'
const api = 'http://127.0.0.1:18000'
const ui = 'http://127.0.0.1:15173'
const temp = await mkdtemp(resolve(tmpdir(), 'keyoushu-e-browser-'))
const db = resolve(temp, 'browser.db')
const events = [], requests = [], errors = [], logs = { backend: '', frontend: '' }
let backend, frontend, browser
const pause = ms => new Promise(r => setTimeout(r, ms))
const record = (name, details = {}) => {
  events.push({ name, at: new Date().toISOString(), ...details })
  console.log('PASS ' + name)
}
async function ready(url, child) {
  for (let i = 0; i < 120; i++) {
    assert.equal(child.exitCode, null, JSON.stringify(logs))
    try { if ((await fetch(url)).ok) return } catch {}
    await pause(100)
  }
  throw new Error('Service did not become ready: ' + url)
}
async function stop(child) {
  if (!child || child.exitCode !== null) return
  const ended = new Promise(r => child.once('exit', r))
  child.kill()
  await ended
}
async function startBackend(fail = false) {
  const code = [
    'import sys', 'from pathlib import Path', 'import database',
    'database.DB_PATH = Path(sys.argv[1])', 'import main', 'import uvicorn',
    'from fastapi.middleware.cors import CORSMiddleware',
    'app = CORSMiddleware(main.app, allow_origins=["http://127.0.0.1:15173"], allow_methods=["*"], allow_headers=["*"])',
    'uvicorn.run(app, host="127.0.0.1", port=18000, log_level="info")',
  ].join('\n')
  const env = { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONDONTWRITEBYTECODE: '1',
    OLLAMA_BASE_URL: 'http://127.0.0.1:11434', OLLAMA_VISION_MODEL: 'qwen2.5vl:7b' }
  delete env.FOLLOWUP_MODEL_PATH
  if (fail) env.FOLLOWUP_MODEL_PATH = resolve(temp, 'intentionally-missing-model.json')
  backend = spawn(python, ['-B', '-c', code, db], { cwd: resolve(root, 'backend'), env, windowsHide: true, stdio: 'pipe' })
  backend.stdout.on('data', d => logs.backend += d)
  backend.stderr.on('data', d => logs.backend += d)
  await ready(api + '/health', backend)
}
try {
  for (const url of [api + '/health', ui]) {
    let occupied = false
    try { await fetch(url); occupied = true } catch {}
    assert.equal(occupied, false, 'Port already in use: ' + url)
  }
  await startBackend()
  frontend = spawn(process.execPath, [resolve(root, 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '15173', '--strictPort'], {
    cwd: resolve(root, 'frontend'), env: { ...process.env, VITE_API_BASE: api }, windowsHide: true, stdio: 'pipe',
  })
  frontend.stdout.on('data', d => logs.frontend += d)
  frontend.stderr.on('data', d => logs.frontend += d)
  await ready(ui, frontend)
  browser = await chromium.launch({ executablePath: process.env.EDGE_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, permissions: ['clipboard-read', 'clipboard-write'], acceptDownloads: true })
  const page = await context.newPage()
  page.on('pageerror', e => errors.push(e.message))
  page.on('response', r => {
    if (r.url().startsWith(api)) requests.push({ method: r.request().method(), path: new URL(r.url()).pathname, status: r.status() })
  })
  page.setDefaultTimeout(15000)
  await page.goto(ui)
  await page.getByRole('button', { name: '开始分析', exact: true }).click()
  await page.getByText('请粘贴聊天原文或上传聊天截图', { exact: true }).waitFor()
  await page.screenshot({ path: resolve(evidence, 'final-browser-empty.png'), fullPage: true })
  record('empty input validation')
  await page.keyboard.press('Control+Shift+D')
  assert.match(await page.locator('#chat-text').inputValue(), /100件/)
  assert.equal(await page.locator('#customer-name').inputValue(), '演示客户')
  const responsePromise = page.waitForResponse(r => r.url() === api + '/analyze' && r.request().method() === 'POST')
  await page.getByRole('button', { name: '开始分析', exact: true }).click()
  const response = await responsePromise
  assert.equal(response.status(), 200)
  const analyzed = await response.json()
  assert.equal(analyzed.is_sample, false)
  assert.deepEqual(Object.keys(analyzed).sort(), ['id', 'requirements', 'questions', 'tasks', 'reply', 'is_sample'].sort())
  await page.locator('#reply-draft').waitFor({ state: 'visible' })
  await page.waitForFunction(() => !document.querySelector('#chat-text').disabled)
  assert.equal(await page.locator('.sample-flag').count(), 0)
  assert.match(await page.locator('.original pre').innerText(), /客户名称：演示客户/)
  const textId = analyzed.id
  await page.screenshot({ path: resolve(evidence, 'final-browser-text.png'), fullPage: true })
  record('demo shortcut and real text analysis', { id: textId, is_sample: analyzed.is_sample })

  const quantityIndex = analyzed.requirements.findIndex(r => r.field === '数量') + 1
  assert.ok(quantityIndex > 0)
  await page.getByRole('textbox', { name: `需求 ${quantityIndex} 值`, exact: true }).fill('100件（人工核对）')
  const editedReply = '已人工核对数量100件，请补充具体年份和尺码分布。'
  await page.locator('#reply-draft').fill(editedReply)
  await page.getByRole('button', { name: '保存修改', exact: true }).click()
  await page.getByText('已保存，刷新或重新打开历史记录可查看', { exact: true }).waitFor()
  await page.reload()
  await page.locator('#reply-draft').waitFor()
  assert.equal(await page.locator('#reply-draft').inputValue(), editedReply)
  assert.equal(await page.getByRole('textbox', { name: `需求 ${quantityIndex} 值`, exact: true }).inputValue(), '100件（人工核对）')
  await page.getByRole('button', { name: /客户名称：演示客户/ }).click()
  await page.waitForFunction(() => !document.querySelector('#chat-text').disabled)
  await page.getByRole('button', { name: '复制回复', exact: true }).click()
  await page.getByText('回复草稿已复制', { exact: true }).waitFor()
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), editedReply)
  await page.locator('#reply-draft').fill(editedReply + ' 导出前补充。')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出需求单 JSON', exact: true }).click()
  const download = await downloadPromise
  await download.saveAs(resolve(evidence, 'final-browser-text-export.json'))
  const exported = JSON.parse(await readFile(await download.path(), 'utf8'))
  assert.equal(exported.id, textId)
  assert.equal(exported.result.reply, editedReply + ' 导出前补充。')
  assert.equal(exported.result.is_sample, false)
  assert.match(exported.text, /100件/)
  record('edit save reload history clipboard dirty export', { id: textId, filename: download.suggestedFilename() })

  await stop(backend)
  await startBackend(true)
  await page.locator('#customer-name').fill('独立验收错误重试')
  await page.locator('#chat-text').fill('客户：先做100件。\n客户：数量改成150件，其他要求后面再说。')
  const failPromise = page.waitForResponse(r => r.url() === api + '/analyze' && r.request().method() === 'POST')
  await page.getByRole('button', { name: '开始分析', exact: true }).click()
  assert.equal((await failPromise).status(), 500)
  await page.locator('main > .error').filter({ hasText: '模型调用失败，请稍后重试' }).waitFor()
  assert.match(await page.locator('#chat-text').inputValue(), /150件/)
  assert.equal(await page.getByRole('button', { name: '开始分析', exact: true }).isEnabled(), true)
  await page.screenshot({ path: resolve(evidence, 'final-browser-model-error.png'), fullPage: true })
  record('real backend model failure displayed; input retained', { injection: 'FOLLOWUP_MODEL_PATH set to nonexistent file; no model substitute' })
  await stop(backend)
  await startBackend()
  const retryPromise = page.waitForResponse(r => r.url() === api + '/analyze' && r.request().method() === 'POST')
  await page.getByRole('button', { name: '开始分析', exact: true }).click()
  const retried = await (await retryPromise).json()
  await page.waitForFunction(() => !document.querySelector('#chat-text').disabled)
  assert.equal(retried.is_sample, false)
  assert.ok(retried.requirements.some(r => r.field === '数量' && /150/.test(r.value) && !/100/.test(r.value)))
  assert.equal(await page.locator('main > .error').count(), 0)
  record('same input retry after model configuration recovery', { id: retried.id })

  await stop(backend)
  await page.getByRole('button', { name: '开始分析', exact: true }).click()
  await page.locator('main > .error').filter({ hasText: '无法连接后端服务' }).waitFor()
  record('backend offline network error visible')
  await startBackend()
  const invalidRoute = route => route.continue({ postData: JSON.stringify({ text: 123 }) })
  await page.route(api + '/analyze', invalidRoute)
  const invalidPromise = page.waitForResponse(r => r.url() === api + '/analyze' && r.request().method() === 'POST')
  await page.getByRole('button', { name: '开始分析', exact: true }).click()
  assert.equal((await invalidPromise).status(), 422)
  await page.locator('main > .error').filter({ hasText: '聊天原文：请填写文字' }).waitFor()
  await page.unroute(api + '/analyze', invalidRoute)
  const historyRoute = route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '验收注入：历史暂时不可用' }) })
  await page.route(api + '/records', historyRoute)
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await page.locator('.record-list .error').filter({ hasText: '历史暂时不可用' }).waitFor()
  assert.match(await page.locator('main > .error').innerText(), /聊天原文：请填写文字/)
  await page.unroute(api + '/records', historyRoute)
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await page.waitForFunction(() => !document.querySelector('.record-list .error'))
  assert.match(await page.locator('main > .error').innerText(), /聊天原文：请填写文字/)
  await page.screenshot({ path: resolve(evidence, 'final-browser-validation.png'), fullPage: true })
  record('actual 422 readable field message and independent history failure recovery', {
    injection: 'POST body deliberately changed to text:number for real 422; GET list 500 response injected',
  })

  await page.getByRole('button', { name: '清空', exact: true }).click()
  await page.locator('input[type=file]').setInputFiles(resolve(root, 'samples/screenshots/roles.png'))
  await page.locator('.preview').waitFor()
  const imageStart = Date.now()
  const imagePromise = page.waitForResponse(r => r.url() === api + '/analyze' && r.request().method() === 'POST', { timeout: 650000 })
  await page.getByRole('button', { name: '开始分析', exact: true }).click()
  await page.getByRole('button', { name: '分析中…', exact: true }).waitFor()
  assert.equal(await page.locator('#chat-text').isDisabled(), true)
  assert.equal(await page.locator('#reply-draft').isDisabled(), true)
  await page.screenshot({ path: resolve(evidence, 'final-browser-image-loading.png'), fullPage: true })
  const imageResponse = await imagePromise
  assert.equal(imageResponse.status(), 200)
  const imageResult = await imageResponse.json()
  await page.waitForFunction(() => !document.querySelector('#chat-text').disabled)
  await page.locator('.source-image img').waitFor()
  assert.ok(await page.locator('.source-image img').evaluate(img => img.complete && img.naturalWidth > 0))
  assert.equal(imageResult.is_sample, false)
  const imageRecord = await (await fetch(api + '/records/' + imageResult.id)).json()
  const originalBytes = await readFile(resolve(root, 'samples/screenshots/roles.png'))
  assert.equal(imageRecord.source_image, 'data:image/png;base64,' + originalBytes.toString('base64'))
  assert.ok(imageRecord.source_transcript.trim())
  assert.ok(imageResult.requirements.every(r => imageRecord.text.includes(r.evidence)))
  assert.ok(imageResult.requirements.some(r => r.field === '数量' && /150/.test(r.value)))
  assert.ok(!imageResult.requirements.some(r => r.value.includes('初步方案')))
  await page.screenshot({ path: resolve(evidence, 'final-browser-image.png'), fullPage: true })
  await writeFile(resolve(evidence, 'final-browser-image-record.json'), JSON.stringify(imageRecord, null, 2))
  record('real image upload loading role extraction exact original image and transcript', { id: imageResult.id, seconds: (Date.now() - imageStart) / 1000 })
  const imageReply = imageResult.reply + ' 已人工核对原图。'
  await page.locator('#reply-draft').fill(imageReply)
  await page.getByRole('button', { name: '保存修改', exact: true }).click()
  await page.getByText('已保存，刷新或重新打开历史记录可查看', { exact: true }).waitFor()
  await stop(backend)
  await startBackend()
  await page.reload()
  await page.locator('.source-image img').waitFor()
  assert.equal(await page.locator('.source-image img').getAttribute('src'), imageRecord.source_image)
  assert.equal(await page.locator('#reply-draft').inputValue(), imageReply)
  await page.getByRole('button', { name: /客户名称：演示客户/ }).click()
  await page.waitForFunction(() => !document.querySelector('#chat-text').disabled)
  assert.equal(await page.locator('.source-image img').count(), 0)
  await page.getByRole('button', { name: /聊天截图转录/ }).click()
  await page.locator('.source-image img').waitFor()
  const imageDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出需求单 JSON', exact: true }).click()
  const imageDownload = await imageDownloadPromise
  await imageDownload.saveAs(resolve(evidence, 'final-browser-image-export.json'))
  const imageExport = JSON.parse(await readFile(await imageDownload.path(), 'utf8'))
  assert.equal(imageExport.source_image, imageRecord.source_image)
  assert.equal(imageExport.source_transcript, imageRecord.source_transcript)
  assert.equal(imageExport.result.reply, imageReply)
  record('image edit save and backend restart persist original image; history switch clears old image; image export complete')

  // UI-only injection validates the old development-source banner, separately from real-model runs.
  const sampleRoute = async route => {
    const r = await route.fetch()
    const body = await r.json()
    body.result.is_sample = true
    await route.fulfill({ response: r, json: body })
  }
  await page.route(api + '/records/' + imageResult.id, sampleRoute)
  await page.reload()
  await page.locator('.sample-flag').waitFor()
  await page.screenshot({ path: resolve(evidence, 'final-browser-sample-banner-injected.png'), fullPage: true })
  record('development sample banner', { injection: 'GET detail response flag only; not real model output' })
  await page.unroute(api + '/records/' + imageResult.id, sampleRoute)
  await page.reload()
  await page.locator('.source-image img').waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: resolve(evidence, 'final-browser-mobile.png'), fullPage: true })
  const mobile = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }))
  record('mobile layout measured', mobile)
  assert.deepEqual(errors, [])
  record('no uncaught browser pageerror')
} catch (e) {
  events.push({ name: 'FAILED', error: e.stack })
  throw e
} finally {
  if (browser) await browser.close()
  await stop(backend)
  await stop(frontend)
  await writeFile(resolve(evidence, 'final-browser-results.json'), JSON.stringify({ root, db, ports: [18000, 15173], events, requests, errors, logs, servicesStopped: true }, null, 2))
}
