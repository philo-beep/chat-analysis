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
const temp = await mkdtemp(resolve(tmpdir(), 'keyoushu-calendar-'))
const api = 'http://127.0.0.1:18000', ui = 'http://127.0.0.1:15173'
const checks = [], errors = [], children = [], logs = []
const pass = (name) => { checks.push(name); console.log('PASS ' + name) }
// 页面沿用按钮颜色过渡；等待最终渲染色，避免在动画中间帧误报。
async function assertColor(locator, expected) {
  let actual
  for (let attempt = 0; attempt < 40; attempt++) {
    actual = await locator.evaluate(node => getComputedStyle(node).backgroundColor)
    if (actual === expected) return
    await new Promise(resolve => setTimeout(resolve, 50))
  }
  assert.equal(actual, expected)
}
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
import calendar_store
from datetime import timedelta
user = auth_store.create_user('directory_tester', 'Directory-test-2026', ['member'])
auth_store.create_user('directory_empty', 'Directory-test-2026', ['member'])
auth_store.create_user('calendar_viewer', 'Directory-test-2026', ['viewer'])
other = auth_store.create_user('directory_other', 'Directory-test-2026', ['member'])
due = (calendar_store.today()+timedelta(days=6)).isoformat()
result = dict(requirements=[dict(field='品类', value='礼盒', evidence='礼盒')], questions=['交货日期是否确定？'], tasks=['联系甲方确认颜色', f'DDL: {due} 提交报价'], reply='已收到礼盒需求。', is_sample=False)
text = '长对话测试礼盒\\n' + ('甲：请确认礼盒报价与交期。\\n乙：周五提供方案，请先确认颜色。\\n' * 100) + '原文末尾标记'
database.save_record(text, result, source_input={'text': text}, owner_id=user['id'])
stream = io.BytesIO()
Image.new('RGB', (60, 100), 'white').save(stream, format='PNG')
image = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
database.save_record('截图测试礼盒', dict(requirements=[], questions=[], tasks=['核对截图与转录'], reply='请核对截图。', is_sample=False), source_image=image, source_transcript='甲：请确认礼盒。乙：收到。', owner_id=user['id'])
database.save_record('其他账号记录', dict(requirements=[], questions=[], tasks=['不应泄露的任务'], reply='', is_sample=False), owner_id=other['id'])
for i in range(6):
    calendar_store.create_item(user['id'], dict(title=f'点数测试{i}', due_date=(calendar_store.today()+timedelta(days=10)).isoformat()))
old = calendar_store.create_item(user['id'], dict(title='逾期虚线测试', due_date=(calendar_store.today()-timedelta(days=1)).isoformat()))
with database._connect() as conn:
    conn.execute('UPDATE task_items SET start_date=? WHERE id=?', ((calendar_store.today()-timedelta(days=4)).isoformat(), old['id']))
calendar_store.create_item(other['id'], dict(title='其他用户的秘密事项'))
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
  await nav('日程计划').click()
  const panel = page.getByRole('region', { name: '日程计划', exact: true })
  const dialog = page.getByRole('dialog', { name: '事件详情', exact: true })
  const pool = page.getByRole('region', { name: '无 DDL 待办池', exact: true })
  const token = await page.evaluate(() => localStorage.getItem('keyoushu.auth.token'))
  async function apiRequest(path = '', options = {}) {
    const response = await fetch(api + '/api/calendar/items' + path, { ...options, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } })
    const body = await response.json()
    assert.equal(response.status, 200, JSON.stringify(body))
    return body.data
  }
  async function recordsRequest(path, options = {}) {
    return fetch(api + '/api/records' + path, { ...options, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } })
  }
  const historyResponse = await recordsRequest('')
  assert.equal(historyResponse.status, 200)
  const history = (await historyResponse.json()).data
  const longChat = history.find(record => record.title.startsWith('长对话测试礼盒'))
  assert.ok(longChat)
  const analysisLinked = (await apiRequest('?status=all')).items.filter(item => item.source_record_id === longChat.id)
  assert.equal(analysisLinked.length, 2)
  assert.equal(analysisLinked.find(item => item.title === '联系甲方确认颜色').due_date, null)
  assert.match(analysisLinked.find(item => item.title.startsWith('DDL:')).due_date, /^\d{4}-\d{2}-\d{2}$/)
  assert.equal((await apiRequest('?scheduled=false')).items.some(item => item.source_record_id === longChat.id && item.title === '联系甲方确认颜色'), true)
  pass('聊天分析待办自动同步：无明确 DDL 进入待办池，明确日期直接排期并使用自动等级')
  const initial = await apiRequest('?status=all')
  const today = initial.today
  const dateAdd = (n) => new Date(Date.parse(today + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10)
  await panel.getByRole('button', { name: '+ 新增待办', exact: true }).waitFor()
  assert.match(page.url(), /#\/calendar$/)
  assert.equal(await nav('日程计划').getAttribute('aria-current'), 'page')
  const day = (date) => panel.locator(`.day[data-date="${date}"]`)
  assert.equal(await day(today).locator('.dot').count(), 5)
  await day(today).getByRole('button', { name: /全部 7 件事件/ }).click()
  assert.equal(await panel.getByRole('region', { name: '选中日期的事件' }).locator('li').count(), 7)
  pass('独立日程入口无需选择聊天；每日最多五点，+n 打开完整当日列表')

  await pool.getByRole('button', { name: '+ 新增待办', exact: true }).click()
  const create = page.getByRole('dialog', { name: '新增待办', exact: true })
  await create.getByRole('textbox', { name: /标题/ }).fill('验收：交付业务方案')
  await create.getByRole('button', { name: '保存', exact: true }).click()
  await create.waitFor({ state: 'hidden' })
  const row = pool.locator('li').filter({ hasText: '验收：交付业务方案' })
  await row.waitFor()
  let item = (await apiRequest('?scheduled=false')).items.find(item => item.title === '验收：交付业务方案')
  assert.ok(item)
  assert.equal(item.start_date, null)
  assert.equal(item.effective_start_date, today)
  pass('1. 新增无 DDL 待办，真实持久化到待办池')

  await row.getByRole('button', { name: '设 DDL', exact: true }).click()
  await dialog.locator('input[type="date"]').fill(dateAdd(3))
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' })
  assert.equal(await row.count(), 0)
  await assertColor(day(today).getByRole('button', { name: /验收：交付业务方案/ }), 'rgb(234, 88, 12)')
  for (let i = 0; i <= 3; i++) {
    const date = dateAdd(i)
    await day(date).getByRole('button', { name: new RegExp(`${date} 全部`) }).click()
    await panel.getByRole('region', { name: '选中日期的事件' }).getByRole('button', { name: /验收：交付业务方案/ }).click()
    assert.match(await dialog.textContent(), /自动 4 级/)
    await dialog.getByRole('button', { name: '取消', exact: true }).click()
  }
  pass('2. 设置三天后 DDL，创建日至 DDL 四天均可访问，自动四级橙色')

  await panel.getByRole('region', { name: '选中日期的事件' }).getByRole('button', { name: /验收：交付业务方案/ }).click()
  await dialog.getByRole('combobox', { name: '紧迫等级' }).selectOption('5')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' })
  item = await apiRequest('/' + item.id)
  assert.equal(item.manual_level, 5)
  await assertColor(day(today).getByRole('button', { name: /验收：交付业务方案/ }), 'rgb(220, 38, 38)')
  // Five-dot limit means the complete day list is used for this item.
  await panel.getByRole('region', { name: '选中日期的事件' }).getByRole('button', { name: /验收：交付业务方案/ }).click()
  assert.match(await dialog.textContent(), /手动 5 级/)
  await dialog.getByRole('button', { name: '恢复自动', exact: true }).click()
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' })
  assert.equal((await apiRequest('/' + item.id)).manual_level, null)
  await panel.getByRole('region', { name: '选中日期的事件' }).getByRole('button', { name: /验收：交付业务方案/ }).click()
  await dialog.getByRole('combobox', { name: '紧迫等级' }).selectOption('5')
  await dialog.locator('input[type="date"]').fill(dateAdd(-1))
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' })
  const anomaly = day(dateAdd(-1)).getByRole('button', { name: /验收：交付业务方案/ })
  await assertColor(anomaly, 'rgb(127, 29, 29)')
  assert.match(await anomaly.getAttribute('class'), /overdue.*anomaly/)
  await panel.getByRole('region', { name: '逾期事项', exact: true }).getByRole('button', { name: /验收：交付业务方案/ }).waitFor()
  pass('3–4. 固定等级与恢复自动可保存；改昨日 DDL 后立即显示深红逾期和反向日期标记')

  await anomaly.click()
  await dialog.getByRole('button', { name: '完成任务', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' })
  assert.equal(await anomaly.count(), 0)
  assert.equal(await panel.getByRole('region', { name: '逾期事项' }).getByRole('button', { name: /验收：交付业务方案/ }).count(), 0)
  await panel.locator('.completed-list summary').click()
  const completed = panel.locator('.completed-list li').filter({ hasText: '验收：交付业务方案' })
  await completed.waitFor()
  assert.ok((await apiRequest('/' + item.id)).completed_at)
  pass('5. 完成任务后圆点与逾期提示消失，完成时间和记录保留')

  await page.keyboard.press('g')
  await panel.getByRole('region', { name: '甘特图', exact: true }).waitFor()
  assert.match(page.url(), /#\/calendar\/gantt$/)
  assert.equal(await panel.locator('.gantt .anomaly').count(), 0)
  await panel.getByRole('checkbox', { name: '显示已完成' }).check()
  const doneAnomaly = panel.getByRole('button', { name: '验收：交付业务方案：截止日早于开始日，请核对日期', exact: true })
  await doneAnomaly.waitFor()
  await assertColor(doneAnomaly, 'rgb(107, 114, 128)')
  // Normal completed item is a gray bar, reverse-date item remains an explicit anomaly.
  const normal = await apiRequest('', { method: 'POST', body: JSON.stringify({ title: '完成横条测试', due_date: dateAdd(2) }) })
  await apiRequest(`/${normal.id}/completion`, { method: 'PATCH', body: JSON.stringify({ completed: true }) })
  await panel.getByRole('button', { name: '刷新日程', exact: true }).click()
  const gray = panel.getByRole('button', { name: /完成横条测试，计划区间/ })
  await gray.waitFor()
  await assertColor(gray, 'rgb(107, 114, 128)')
  assert.ok(await panel.locator('.bar.extension').count())
  await panel.getByRole('button', { name: '周', exact: true }).click()
  assert.equal(await panel.getByRole('button', { name: '周', exact: true }).getAttribute('aria-pressed'), 'true')
  await page.screenshot({ path: resolve(temp, 'gantt-desktop.png'), fullPage: true })
  await page.reload()
  await panel.getByRole('region', { name: '甘特图', exact: true }).waitFor()
  assert.equal(await nav('日程计划').getAttribute('aria-current'), 'page')
  await page.keyboard.press('g')
  await panel.getByRole('group', { name: '月视图日历', exact: true }).waitFor()
  pass('6. G 双向切换、深链接刷新、日周刻度、完成灰条和正常逾期虚线均正确')

  for (const topic of ['日历主体', '手动调整等级', '无 DDL 待办池', '甘特图切换']) {
    await panel.getByRole('button', { name: `${topic}帮助`, exact: true }).click()
    const help = page.getByRole('dialog')
    await help.getByRole('list', { name: '操作流程' }).waitFor()
    assert.equal(await help.locator('.explanation').count(), 2)
    await page.screenshot({ path: resolve(temp, `help-${topic}.png`), fullPage: false })
    await page.keyboard.press('g')
    assert.match(page.url(), /#\/calendar$/)
    await help.getByRole('button', { name: '知道了', exact: true }).click()
  }
  await panel.getByRole('button', { name: '日历主体帮助', exact: true }).click()
  await page.keyboard.press('Escape')
  assert.equal(await page.getByRole('dialog').count(), 0)
  await panel.getByRole('button', { name: '日历主体帮助', exact: true }).click()
  await page.locator('.calendar-overlay').click({ position: { x: 2, y: 2 } })
  assert.equal(await page.getByRole('dialog').count(), 0)
  pass('7. 四个模块帮助均有说明与流程图，知道了/遮罩/Esc 均可关闭，弹层避让 G')

  await panel.locator('.completed-list summary').click()
  await panel.locator('.completed-list li').filter({ hasText: '验收：交付业务方案' }).getByRole('button', { name: '重新打开任务', exact: true }).click()
  await anomaly.waitFor()
  await anomaly.click()
  await dialog.getByRole('textbox', { name: /标题/ }).fill('g')
  await page.keyboard.press('g')
  assert.match(page.url(), /#\/calendar$/)
  // A failed mutation must preserve the editor and not claim completion.
  await page.route(`**/api/calendar/items/${item.id}`, route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 500, message: '模拟保存失败', data: null }) }))
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await dialog.getByRole('alert').filter({ hasText: '模拟保存失败' }).waitFor()
  assert.equal(await dialog.getByRole('textbox', { name: /标题/ }).inputValue(), 'gg')
  await page.unroute(`**/api/calendar/items/${item.id}`)
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await page.screenshot({ path: resolve(temp, 'calendar-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: resolve(temp, 'calendar-mobile.png'), fullPage: true })
  await panel.getByRole('button', { name: /切换到甘特图/ }).click()
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: resolve(temp, 'gantt-mobile.png'), fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  pass('完成可重开，输入时快捷键不冲突；失败保留表单；390px 月历和甘特无页面溢出')

  await nav('建议待办').click()
  await content.getByText('联系甲方确认颜色', { exact: true }).waitFor()
  const source = content.locator('li').filter({ hasText: '联系甲方确认颜色' })
  await source.getByRole('button', { name: '加入待办池', exact: true }).click()
  await page.getByRole('status').filter({ hasText: '已加入日程计划' }).waitFor()
  await source.getByRole('button', { name: '加入待办池', exact: true }).click()
  assert.equal((await apiRequest('?scheduled=false')).items.filter(i => i.title === '联系甲方确认颜色').length, 1)
  await nav('日程计划').click()
  await pool.getByRole('button', { name: '联系甲方确认颜色', exact: true }).waitFor()
  assert.equal(await panel.getByText('其他用户的秘密事项', { exact: true }).count(), 0)

  const screenshotChat = history.find(record => record.title.startsWith('截图测试礼盒'))
  const beforeDelete = await apiRequest('?status=all')
  const screenshotTasks = beforeDelete.items.filter(item => item.source_record_id === screenshotChat.id)
  assert.equal(screenshotTasks.length, 1)
  let warning = ''
  page.once('dialog', async nativeDialog => { warning = nativeDialog.message(); await nativeDialog.dismiss() })
  await page.getByRole('button', { name: '删除聊天记录：截图测试礼盒', exact: true }).click()
  assert.match(warning, /待办池、已排期和已完成事项/)
  assert.equal((await recordsRequest('/' + screenshotChat.id)).status, 200)
  assert.equal((await apiRequest('?status=all')).items.filter(item => item.source_record_id === screenshotChat.id).length, 1)
  pass('取消删除确认后聊天与同步事项都保留')

  await page.route(`**/api/records/${screenshotChat.id}`, route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 500, message: '模拟删除失败', data: null }) }))
  page.once('dialog', async nativeDialog => { warning = nativeDialog.message(); await nativeDialog.accept() })
  await page.getByRole('button', { name: '删除聊天记录：截图测试礼盒', exact: true }).click()
  await page.locator('.record-list').getByRole('alert').filter({ hasText: '模拟删除失败' }).waitFor()
  assert.equal((await recordsRequest('/' + screenshotChat.id)).status, 200)
  assert.equal((await apiRequest('?status=all')).items.filter(item => item.source_record_id === screenshotChat.id).length, 1)
  await page.unroute(`**/api/records/${screenshotChat.id}`)
  pass('删除请求失败时保留聊天与同步日历事项，显示可见错误')

  page.once('dialog', async nativeDialog => { warning = nativeDialog.message(); await nativeDialog.accept() })
  await page.getByRole('button', { name: '删除聊天记录：截图测试礼盒', exact: true }).click()
  assert.match(warning, /待办池、已排期和已完成事项/)
  assert.match(warning, /手工创建的日历事项不受影响/)
  assert.match(warning, /其他用户日历中的事项也不受影响/)
  await page.getByRole('status').filter({ hasText: '同步删除 1 条日历事项' }).waitFor()
  assert.equal((await recordsRequest('/' + screenshotChat.id)).status, 404)
  const afterDelete = await apiRequest('?status=all')
  assert.equal(afterDelete.items.some(item => item.source_record_id === screenshotChat.id), false)
  assert.ok(afterDelete.items.some(item => item.title === '联系甲方确认颜色'))
  pass('删除聊天前清晰提示日历影响；确认后原子删除聊天及来源任务，其他日历任务保留')

  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await login('calendar_viewer')
  await pool.getByText('没有未排期的待办，去加一个吧', { exact: true }).waitFor()
  assert.equal(await pool.getByRole('button', { name: '+ 新增待办', exact: true }).isDisabled(), true)
  assert.equal(await panel.getByText('联系甲方确认颜色', { exact: true }).count(), 0)
  pass('来源建议可导入真实待办池且去重；账号切换隔离；只读账号不能写入')
  assert.deepEqual(errors, [])
  await writeFile(resolve(temp, 'results.json'), JSON.stringify({ checks, errors, fixture: '临时数据库和真实 HTTP，非模型输出验收' }, null, 2))
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
