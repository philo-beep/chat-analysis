// Isolated customer pages, real login/HTTP/database; no cloud model requests.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_NODE_MODULES ? resolve(process.env.PLAYWRIGHT_NODE_MODULES, 'playwright') : 'playwright')

const root = fileURLToPath(new URL('../..', import.meta.url))
const temp = await mkdtemp(resolve(tmpdir(), 'keyoushu-customers-browser-'))
const api = 'http://127.0.0.1:18000', ui = 'http://127.0.0.1:15173'
const children = [], logs = [], checks = [], errors = []
let browser
function start(command, args, cwd, env = {}) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, windowsHide: true, stdio: 'pipe' })
  child.stdout.on('data', data => logs.push(String(data)))
  child.stderr.on('data', data => logs.push(String(data)))
  child.on('error', error => logs.push(error.message))
  children.push(child)
  return child
}
async function ready(url, child) {
  for (let n = 0; n < 100; n++) {
    assert.equal(child.exitCode, null, logs.join(''))
    try { if ((await fetch(url)).ok) return } catch {}
    await new Promise(r => setTimeout(r, 100))
  }
  throw new Error('Service unavailable: ' + url + '\n' + logs.join(''))
}
const seed = `
import sys
from pathlib import Path
import database
database.DB_PATH = Path(sys.argv[1])
database.init_db()
import auth_store
owner = auth_store.create_user('customer_tester', 'Customer-browser-2026', ['member'])
other = auth_store.create_user('other_customer_tester', 'Customer-browser-2026', ['member'])
result = dict(requirements=[], questions=[], tasks=[], reply='收到。', is_sample=False)
profile = dict(display_name='陈晓明', company='春禾商贸', role='采购负责人', industry='零售', concerns=['交期'], decision_style='需要主管确认', communication_preferences=['先发文字'], risk_points=['避免承诺未经确认的交期'], next_follow_up='发送交期安排', communication_strategy='先确认交期，再讨论方案。', communication_points=['先询问到货时间。','把交货安排写清楚。','确认主管何时能回复。'])
database.save_record('第一次沟通', result, owner_id=owner['id'], customer_profile=profile)
profile.update(communication_strategy='先给阶梯报价，再确认交期。', communication_points=['主动给出阶梯报价。','把可承诺的交期写清楚。','确认主管的审批时间。'], concerns=['价格', '交期'], next_follow_up='发送阶梯报价')
database.save_record('第二次沟通', result, owner_id=owner['id'], customer_profile=profile)
old = dict(display_name='刘晓雨', company='远帆贸易', role='经理', industry='贸易', concerns=[], decision_style='未知', communication_preferences=[], risk_points=[], next_follow_up='未知')
database.save_record('旧画像', result, owner_id=owner['id'], customer_profile=old)
import main, uvicorn
from fastapi.middleware.cors import CORSMiddleware
app = CORSMiddleware(main.app, allow_origins=['http://127.0.0.1:15173'], allow_methods=['*'], allow_headers=['*'])
uvicorn.run(app, host='127.0.0.1', port=18000, log_level='warning')
`
const pass = name => { checks.push(name); console.log('PASS ' + name) }

try {
  for (const url of [api + '/health', ui]) {
    let occupied = false
    try { await fetch(url); occupied = true } catch {}
    assert.equal(occupied, false, 'Test port occupied ' + url)
  }
  const py = process.env.PYTHON_EXECUTABLE || resolve(root, process.platform === 'win32' ? 'backend/.venv/Scripts/python.exe' : 'backend/.venv/bin/python')
  await ready(api + '/health', start(py, ['-B', '-c', seed, resolve(temp, 'test.db')], resolve(root, 'backend'), { KEYOUSHU_JWT_SECRET: 'customer-isolated-browser-secret-2026', PYTHONIOENCODING: 'utf-8' }))
  await ready(ui, start(process.execPath, [resolve(root, 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '15173', '--strictPort'], resolve(root, 'frontend'), { VITE_API_BASE: api }))
  const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  browser = await chromium.launch({ executablePath: process.env.EDGE_EXECUTABLE || (existsSync(edge) ? edge : undefined), headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  page.setDefaultTimeout(12000)
  page.on('pageerror', error => errors.push(error.message))
  async function login(name) {
    const unlock = page.getByRole('button', { name: '点击解锁助手', exact: true })
    if (await unlock.isVisible()) await unlock.click()
    await page.locator('#auth-username').fill(name)
    await page.locator('#auth-password').fill('Customer-browser-2026')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    await page.locator('.layout').waitFor()
  }
  await page.goto(ui)
  await login('customer_tester')
  const nav = page.getByRole('navigation', { name: '内容目录' })
  await nav.getByRole('button', { name: '我的客户', exact: true }).click()
  const list = page.getByRole('region', { name: '我的客户', exact: true })
  await list.getByRole('button', { name: '查看客户：陈晓明', exact: true }).waitFor()
  assert.deepEqual(await list.locator('.customer-card h2').allTextContents(), ['刘晓雨', '陈晓明'])
  await list.getByText('下一步：发送阶梯报价', { exact: true }).waitFor()
  pass('我的客户与日程同级，客户卡片展示资料和建议，按最近整理时间排序')
  await list.getByRole('searchbox', { name: '找客户' }).fill('春禾')
  await list.getByRole('button', { name: '搜索', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.customer-card').length === 1)
  await list.getByRole('button', { name: '查看客户：陈晓明', exact: true }).click()
  const detail = page.getByRole('region', { name: '客户详情', exact: true })
  const guidance = detail.getByRole('region', { name: '沟通指导', exact: true })
  await guidance.getByText('先给阶梯报价，再确认交期。', { exact: true }).waitFor()
  assert.equal(await guidance.locator('li').count(), 3)
  pass('按公司搜索可定位客户，详情顶部突出显示策略和三条沟通要点')
  const timeline = detail.getByRole('region', { name: '画像更新时间线', exact: true })
  assert.equal(await timeline.locator('time').count(), 2)
  await timeline.locator('button').last().click()
  await detail.getByText(/你正在看历史快照/).waitFor()
  await guidance.getByText('先确认交期，再讨论方案。', { exact: true }).waitFor()
  const historicalUrl = page.url()
  await page.reload()
  await detail.getByText(/你正在看历史快照/).waitFor()
  await guidance.getByText('先确认交期，再讨论方案。', { exact: true }).waitFor()
  assert.equal(page.url(), historicalUrl)
  await detail.getByRole('button', { name: '回到最新', exact: true }).click()
  await guidance.getByText('先给阶梯报价，再确认交期。', { exact: true }).waitFor()
  assert.equal(await detail.locator('.history-banner').count(), 0)
  pass('两次分析保存两份快照，可回看历史、刷新保留选择并返回最新')
  await detail.screenshot({ path: resolve(temp, 'customer-detail-desktop.png'), animations: 'disabled' })
  await page.setViewportSize({ width: 320, height: 900 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await detail.screenshot({ path: resolve(temp, 'customer-detail-320.png'), animations: 'disabled' })
  pass('客户详情在320px窄屏无整页横向溢出')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await detail.getByRole('button', { name: '返回我的客户', exact: true }).click()
  await list.getByRole('button', { name: '查看客户：刘晓雨', exact: true }).click()
  await detail.getByText('再聊几次就能给出建议', { exact: true }).waitFor()
  pass('旧画像缺少沟通指导时显示友好提示，详情不白屏')
  const privateUrl = page.url()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await page.locator('.layout').waitFor({ state: 'detached' })
  await login('other_customer_tester')
  await detail.getByRole('alert').waitFor()
  assert.equal(await detail.getByText('刘晓雨', { exact: true }).count(), 0)
  await nav.getByRole('button', { name: '我的客户', exact: true }).click()
  await list.getByText('把和客户的聊天整理一次，这里就会留下客户资料。', { exact: true }).waitFor()
  assert.equal(await list.locator('.customer-card').count(), 0)
  pass('切换账号后列表为空，直接访问他人客户地址也不会显示资料')
  assert.deepEqual(errors, [])
  await writeFile(resolve(temp, 'results.json'), JSON.stringify({ checks, errors, fixture: 'isolated temporary database; no cloud calls', privateRouteTested: new URL(privateUrl).hash }, null, 2))
  console.log('Evidence: ' + temp)
} catch (error) {
  await writeFile(resolve(temp, 'failure.txt'), String(error.stack) + '\n' + logs.join(''))
  console.error('Evidence: ' + temp)
  throw error
} finally {
  if (browser) await browser.close()
  for (const child of children.reverse()) if (child.exitCode === null) { const ended = new Promise(r => child.once('exit', r)); child.kill(); await ended }
}
