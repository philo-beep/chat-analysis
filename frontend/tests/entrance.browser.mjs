// 用临时 SQLite 和真实 HTTP 接口验证；不会改用户 app.db，也不调用图片模型。
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const defaultPython = resolve(root, process.platform === 'win32' ? 'backend/.venv/Scripts/python.exe' : 'backend/.venv/bin/python')
const edgePath = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
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
admin = auth_store.create_user('directory_admin', 'Directory-test-2026', ['admin'])
result = dict(requirements=[dict(field='品类', value='礼盒', evidence='礼盒')], questions=['交货日期是否确定？'], tasks=['联系甲方确认颜色', '周五提交报价'], reply='已收到礼盒需求。', is_sample=False)
text = '长对话测试礼盒\\n' + ('甲：请确认礼盒报价与交期。\\n乙：周五提供方案，请先确认颜色。\\n' * 100) + '原文末尾标记'
database.save_record(text, result, source_input={'text': text}, owner_id=user['id'])
stream = io.BytesIO()
Image.new('RGB', (60, 100), 'white').save(stream, format='PNG')
image = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
database.save_record('截图测试礼盒', dict(requirements=[], questions=[], tasks=['核对截图与转录'], reply='请核对截图。', is_sample=False), source_image=image, source_transcript='甲：请确认礼盒。乙：收到。', owner_id=user['id'])
database.save_record('其他账号记录', dict(requirements=[], questions=[], tasks=['不应泄露的任务'], reply='', is_sample=False), owner_id=other['id'])
database.save_record('管理员自有记录', dict(requirements=[], questions=[], tasks=[], reply='', is_sample=False), owner_id=admin['id'])
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
  const backend = start(process.env.PYTHON_EXECUTABLE || defaultPython,
    ['-B', '-c', seed, resolve(temp, 'test.db')], resolve(root, 'backend'), {
      KEYOUSHU_JWT_SECRET: 'isolated-directory-browser-test-secret-2026', PYTHONIOENCODING: 'utf-8',
    })
  await ready(api + '/health', backend)
  const frontend = start(process.execPath, [resolve(root, 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '15173', '--strictPort'],
    resolve(root, 'frontend'), { VITE_API_BASE: api })
  await ready(ui, frontend)
  browser = await chromium.launch({ executablePath: process.env.EDGE_EXECUTABLE || (existsSync(edgePath) ? edgePath : undefined), headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
  const page = await context.newPage()
  page.on('pageerror', (error) => errors.push(error.message))
  page.setDefaultTimeout(15000)

  await page.goto(ui)
  const unlock = page.getByRole('button', { name: '点击解锁助手', exact: true })
  await unlock.waitFor()
  assert.equal(await page.locator('#auth-username').count(), 0)
  await page.screenshot({ path: resolve(temp, 'welcome-desktop.png'), fullPage: true, animations: 'disabled' })
  const card = page.locator('.conversation-card')
  assert.notEqual(await card.evaluate(el => getComputedStyle(el).animationName), 'none')
  await page.getByRole('button', { name: '暂停动效', exact: true }).click()
  assert.equal(await card.evaluate(el => getComputedStyle(el).animationPlayState), 'paused')
  await page.getByRole('button', { name: '继续动效', exact: true }).click()
  assert.equal(await card.evaluate(el => getComputedStyle(el).animationPlayState), 'running')
  pass('欢迎页先于表单展示，动态流程可暂停与恢复')

  await unlock.click()
  await page.locator('#auth-username').waitFor()
  await page.locator('.auth-layout').evaluate(async el => { await Promise.all(el.getAnimations().filter(a => a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {}))) })
  assert.equal(await page.locator('#auth-username').evaluate(el => document.activeElement === el), true)
  await page.screenshot({ path: resolve(temp, 'login-desktop.png'), fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: '返回客有数', exact: true }).click()
  await unlock.waitFor()
  assert.equal(await unlock.evaluate(el => document.activeElement === el), true)
  await page.getByRole('button', { name: '暂停动效', exact: true }).click()
  await unlock.press('Enter')
  assert.equal(await page.locator('.auth-layout').evaluate(el => getComputedStyle(el).opacity), '1')
  await page.locator('#auth-username').fill('directory_tester')
  await page.locator('#auth-password').fill('Wrong-password-2026')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.locator('.login-card .error').waitFor()
  pass('欢迎/登录键盘切换与焦点正确，错误密码仍显示提示')

  await page.getByRole('button', { name: '没有账号？去注册', exact: true }).click()
  assert.match(await page.locator('#auth-password-hint').textContent(), /10–128/)
  await page.locator('#auth-username').fill('directory_tester')
  await page.locator('#auth-password').fill('Entrance-test-2026')
  await page.getByRole('button', { name: '注册', exact: true }).click()
  await page.getByText('用户名已存在，请更换用户名。', { exact: true }).waitFor()
  await page.locator('#auth-username').fill('entrance_new_user')
  await page.getByRole('button', { name: '注册', exact: true }).click()
  await page.getByText('注册成功，请使用刚设置的账号和密码登录。', { exact: true }).waitFor()
  await page.locator('#auth-password').fill('Entrance-test-2026')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.locator('.layout').waitFor()
  await page.locator('.art-brief').evaluate(async el => { await Promise.all(el.getAnimations().map(a => a.finished.catch(() => {}))) })
  await page.screenshot({ path: resolve(temp, 'workspace-desktop.png'), fullPage: true, animations: 'disabled' })
  await page.reload()
  await page.locator('.layout').waitFor()
  assert.equal(await unlock.count(), 0)
  pass('注册提示与重复用户名校验保留，新用户可注册登录，刷新已登录会话直接恢复工作台')

  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await unlock.waitFor()
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'welcome overflow '+width)
    await page.screenshot({ path: resolve(temp, `welcome-${width}.png`), fullPage: true, animations: 'disabled' })
    await unlock.click()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'login overflow '+width)
    await page.screenshot({ path: resolve(temp, `login-${width}.png`), fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: '没有账号？去注册', exact: true }).click()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'register overflow '+width)
    await page.screenshot({ path: resolve(temp, `register-${width}.png`), fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: '已有账号？去登录', exact: true }).click()
    await page.getByRole('button', { name: '返回客有数', exact: true }).click()
  }
  pass('390px 与 320px 欢迎/登录/注册无横向溢出')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  assert.equal(await card.evaluate(el => getComputedStyle(el).animationName), 'none')
  await unlock.click()
  assert.equal(await page.locator('.auth-glow').evaluate(el => getComputedStyle(el).animationName), 'none')
  pass('减少动态效果设置下欢迎与登录背景均静止')
  await page.locator('#auth-username').fill('entrance_new_user')
  await page.locator('#auth-password').fill('Entrance-test-2026')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.locator('.layout').waitFor()
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'workspace overflow 320')
  await page.screenshot({ path: resolve(temp, 'workspace-320.png'), fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await unlock.waitFor()
  await page.goto(ui + '/#/calendar')
  await unlock.click()
  await page.locator('#auth-username').fill('directory_tester')
  await page.locator('#auth-password').fill('Directory-test-2026')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('region', { name: '日程计划', exact: true }).waitFor()
  assert.match(page.url(), /#\/calendar$/)
  pass('窄屏工作台正常，未登录日历深链接经过两段式入口后仍保留')
  assert.deepEqual(errors, [])
  await writeFile(resolve(temp, 'results.json'), JSON.stringify({ checks, errors, fixture: '临时数据库和合成测试账号；未调用云端 AI' }, null, 2))
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
