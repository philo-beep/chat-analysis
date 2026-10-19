// 用临时 SQLite 和真实 HTTP 接口验证；不会改用户 app.db，也不调用图片模型。
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_NODE_MODULES
  ? resolve(process.env.PLAYWRIGHT_NODE_MODULES, 'playwright') : 'playwright')
const temp = await mkdtemp(resolve(tmpdir(), 'keyoushu-directory-'))
const api = 'http://127.0.0.1:18000', ui = 'http://127.0.0.1:15173'
const checks = [], errors = [], children = [], logs = []
const pass = (name) => { checks.push(name); console.log('PASS ' + name) }
let browser
function start(command, args, cwd, env) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, windowsHide: true, stdio: 'pipe' })
  child.on('error', (error) => logs.push(error.message))
  child.stdout.on('data', (data) => logs.push(String(data)))
  child.stderr.on('data', (data) => logs.push(String(data)))
  children.push(child)
  return child
}
async function ready(url, child) {
  for (let i = 0; i < 150; i++) {
    assert.equal(child.exitCode, null, logs.join(''))
    try { if ((await fetch(url)).ok) return } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error('Service unavailable: ' + url + '\n' + logs.join(''))
}
const seed = `
import sys, base64, io
from pathlib import Path
from PIL import Image
import database
database.DB_PATH = Path(sys.argv[1])
database.init_db()
import auth_store
user = auth_store.create_user('directory_tester', 'Directory-test-2026', ['member'])
auth_store.create_user('directory_empty', 'Directory-test-2026', ['member'])
other = auth_store.create_user('directory_other', 'Directory-test-2026', ['member'])
result = dict(requirements=[dict(field='品类', value='礼盒', evidence='礼盒')], questions=['交货日期是否确定？'], tasks=['联系甲方确认颜色', '周五提交报价'], reply='已收到礼盒需求。', is_sample=False)
text = '长对话测试礼盒\\n' + ('甲：请确认礼盒报价与交期。\\n乙：周五提供方案，请先确认颜色。\\n' * 100) + '原文末尾标记'
database.save_record(text, result, source_input={'text': text}, owner_id=user['id'])
stream = io.BytesIO()
Image.new('RGB', (60, 100), 'white').save(stream, format='PNG')
image = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
database.save_record('截图测试礼盒', dict(requirements=[], questions=[], tasks=['核对截图与转录'], reply='请核对截图。', is_sample=False), source_image=image, source_transcript='甲：请确认礼盒。乙：收到。', owner_id=user['id'])
database.save_record('其他账号记录', dict(requirements=[], questions=[], tasks=['不应泄露的任务'], reply='', is_sample=False), owner_id=other['id'])
import main, uvicorn
from fastapi.middleware.cors import CORSMiddleware
app = CORSMiddleware(main.app, allow_origins=['http://127.0.0.1:15173'], allow_methods=['*'], allow_headers=['*'])
uvicorn.run(app, host='127.0.0.1', port=18000, log_level='warning')
`

try {
  for (const url of [api + '/health', ui]) {
    let occupied = false
    try { await fetch(url); occupied = true } catch {}
    assert.equal(occupied, false, '测试端口已占用：' + url)
  }
  const backend = start(process.env.PYTHON_EXECUTABLE || resolve(root, 'backend/.venv/Scripts/python.exe'),
    ['-B', '-c', seed, resolve(temp, 'test.db')], resolve(root, 'backend'), {
      KEYOUSHU_JWT_SECRET: 'isolated-directory-browser-test-secret-2026', PYTHONIOENCODING: 'utf-8',
    })
  await ready(api + '/health', backend)
  const frontend = start(process.execPath, [resolve(root, 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '15173', '--strictPort'],
    resolve(root, 'frontend'), { VITE_API_BASE: api })
  await ready(ui, frontend)
  browser = await chromium.launch({ executablePath: process.env.EDGE_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
  const page = await context.newPage()
  page.on('pageerror', (error) => errors.push(error.message))
  page.setDefaultTimeout(15000)
  const nav = (label) => page.getByRole('navigation', { name: '内容目录' }).getByRole('button', { name: new RegExp(label) })
  const content = page.locator('.record-content')
  const login = async (username = 'directory_tester') => {
    await page.locator('#auth-username').fill(username)
    await page.locator('#auth-password').fill('Directory-test-2026')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    await page.locator('.layout').waitFor()
  }
  await page.goto(ui)
  await login()
  await page.locator('.sidebar .record-list .item').filter({ hasText: '长对话测试礼盒' }).click()
  const original = page.locator('details.original')
  assert.equal(await original.evaluate((element) => element.open), false)
  await original.locator('summary').click()
  assert.equal(await original.evaluate((element) => element.open), true)
  assert.match(await original.locator('pre').textContent(), /原文末尾标记$/)
  assert.equal(await original.locator('.original-content').evaluate((element) => element.scrollHeight > element.clientHeight), true)
  await original.locator('summary').click()
  assert.equal(await original.evaluate((element) => element.open), false)
  await page.screenshot({ path: resolve(temp, 'original-collapsed.png'), fullPage: true })
  pass('长原文默认折叠，展开完整可滚动并可再次收起')

  await page.getByRole('textbox', { name: '建议待办 1', exact: true }).fill('草稿暂存，不应丢失')
  await nav('建议待办').click()
  await content.getByText('联系甲方确认颜色', { exact: true }).waitFor()
  assert.equal(await content.locator('.item').count(), 3)
  assert.match(page.url(), /#\/tasks$/)
  assert.equal(await nav('建议待办').getAttribute('aria-current'), 'page')
  assert.equal(await page.getByText('不应泄露的任务', { exact: true }).count(), 0)
  await content.locator('.item').filter({ hasText: '联系甲方确认颜色' }).click()
  assert.equal(await page.getByRole('textbox', { name: '建议待办 1', exact: true }).inputValue(), '草稿暂存，不应丢失')
  pass('建议待办真实汇总、来源跳转和未保存草稿保留，其他账号数据不可见')

  await page.getByRole('button', { name: '保存修改', exact: true }).click()
  await page.getByText('已保存，刷新或重新打开历史记录可查看', { exact: true }).waitFor()
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出需求单 JSON', exact: true }).click()
  assert.equal((await downloaded).suggestedFilename(), 'record-1.json')
  await nav('建议待办').click()
  await content.getByText('草稿暂存，不应丢失', { exact: true }).waitFor()
  assert.equal(await content.getByText('联系甲方确认颜色', { exact: true }).count(), 0)
  await page.reload()
  await content.getByText('草稿暂存，不应丢失', { exact: true }).waitFor()
  assert.equal(await nav('建议待办').getAttribute('aria-current'), 'page')
  pass('原有保存与导出成功，保存后的内容同步到分类列表')

  await nav('待确认事项').click()
  await content.getByText('交货日期是否确定？', { exact: true }).waitFor()
  await page.reload()
  await content.getByText('交货日期是否确定？', { exact: true }).waitFor()
  assert.equal(await nav('待确认事项').getAttribute('aria-current'), 'page')
  await nav('聊天截图').click()
  await content.locator('img').waitFor()
  assert.equal(await content.locator('.item').count(), 1)
  await page.reload()
  await content.locator('img').waitFor()
  assert.equal(await nav('聊天截图').getAttribute('aria-current'), 'page')
  await page.goBack()
  await content.getByRole('heading', { name: /待确认事项/ }).waitFor()
  await nav('聊天截图').click()
  await content.locator('.item').click()
  assert.equal(await original.evaluate((element) => element.open), false)
  await original.locator('summary').click()
  assert.equal(await original.locator('img').isVisible(), true)
  await original.locator('summary').click()
  pass('问题与截图分类、刷新选中态、浏览器返回及切换记录重置折叠均正确')

  await nav('聊天截图').click()
  await page.setViewportSize({ width: 390, height: 844 })
  for (const label of ['历史记录', '建议待办', '待确认事项', '聊天截图']) assert.equal(await nav(label).isVisible(), true)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true)
  await page.screenshot({ path: resolve(temp, 'mobile.png'), fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.screenshot({ path: resolve(temp, 'desktop.png'), fullPage: true })
  pass('手机宽度目录可用，页面无横向溢出')

  await nav('建议待办').click()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await login('directory_empty')
  await content.getByText('这些记录中还没有建议待办', { exact: true }).waitFor()
  assert.equal(await content.locator('.item').count(), 0)
  await nav('待确认事项').click()
  await content.getByText('这些记录中还没有待确认事项', { exact: true }).waitFor()
  await nav('聊天截图').click()
  await content.getByText('这些记录中还没有保存聊天截图', { exact: true }).waitFor()
  pass('切换账号清除旧数据，三个分类空状态均正确')

  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await page.route('**/records/1', (route) => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '测试：单条详情读取失败' }) }))
  await login()
  await nav('建议待办').click()
  await content.getByRole('alert').filter({ hasText: '当前结果可能不完整' }).waitFor()
  await content.getByText('核对截图与转录', { exact: true }).waitFor()
  await page.unroute('**/records/1')
  await content.getByRole('button', { name: '刷新', exact: true }).click()
  await content.getByText('草稿暂存，不应丢失', { exact: true }).waitFor()
  assert.equal(await content.getByRole('alert').count(), 0)
  pass('部分详情失败明确提示，其他数据可见，刷新可恢复')

  await page.route('**/records', (route) => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '测试：列表读取失败' }) }))
  await content.getByRole('button', { name: '刷新', exact: true }).click()
  await content.getByRole('alert').filter({ hasText: '列表读取失败' }).waitFor()
  assert.equal(await content.getByText('这些记录中还没有建议待办', { exact: true }).count(), 0)
  await nav('待确认事项').click()
  await content.getByRole('alert').filter({ hasText: '列表读取失败' }).waitFor()
  await page.unroute('**/records')
  await content.getByRole('button', { name: '刷新', exact: true }).click()
  await content.getByText('交货日期是否确定？', { exact: true }).waitFor()
  pass('列表失败不误报空数据，切换分类保留错误，重试可恢复')
  assert.deepEqual(errors, [])
  await writeFile(resolve(temp, 'results.json'), JSON.stringify({ checks, errors, fixture: '临时数据库中的合成测试记录，非模型分析验收' }, null, 2))
  console.log('Evidence: ' + temp)
} catch (error) {
  await writeFile(resolve(temp, 'failure.txt'), String(error.stack) + '\n' + logs.join(''))
  console.error('Evidence: ' + temp)
  throw error
} finally {
  if (browser) await browser.close()
  for (const child of children.reverse()) {
    if (child.exitCode === null) {
      const ended = new Promise((resolve) => child.once('exit', resolve))
      child.kill()
      await ended
    }
  }
}
