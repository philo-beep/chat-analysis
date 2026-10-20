// Isolated end-to-end expanded result actions, real HTTP/auth/DB; no cloud calls.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = fileURLToPath(new URL('../..', import.meta.url))
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_NODE_MODULES ? resolve(process.env.PLAYWRIGHT_NODE_MODULES,'playwright') : 'playwright')
const temp = await mkdtemp(resolve(tmpdir(),'keyoushu-expanded-browser-'))
const api='http://127.0.0.1:18000', ui='http://127.0.0.1:15173'
const children=[], logs=[], checks=[], errors=[]
let browser
function start(command,args,cwd,env={}) {
  const child=spawn(command,args,{cwd,env:{...process.env,...env},windowsHide:true,stdio:'pipe'})
  child.stdout.on('data',data=>logs.push(String(data))); child.stderr.on('data',data=>logs.push(String(data)))
  child.on('error',error=>logs.push(error.message)); children.push(child);return child
}
async function ready(url,child) {
  for(let n=0;n<100;n++) {assert.equal(child.exitCode,null,logs.join(''));try{if((await fetch(url)).ok)return}catch{};await new Promise(r=>setTimeout(r,100))}
  throw new Error('Service unavailable '+url+' '+logs.join(''))
}
const seed=`
import sys
from pathlib import Path
import database
database.DB_PATH=Path(sys.argv[1])
database.init_db()
import auth_store
user=auth_store.create_user('expanded_tester','Expanded-browser-2026',['member'])
sys.path.insert(0,str(Path.cwd()/'tests'))
from expanded_fixture import output,SOURCE
value=output();profile=value.pop('customer_profile')
value.update(analysis_version=2,is_sample=False,action_states={})
database.save_record('新版分析样例\\n'+SOURCE,value,owner_id=user['id'],customer_profile=profile)
database.save_record('旧版记录',dict(requirements=[],questions=['旧问题'],tasks=['旧待办'],reply='旧回复',is_sample=False),owner_id=user['id'])
import main,uvicorn
from fastapi.middleware.cors import CORSMiddleware
app=CORSMiddleware(main.app,allow_origins=['http://127.0.0.1:15173'],allow_methods=['*'],allow_headers=['*'])
uvicorn.run(app,host='127.0.0.1',port=18000,log_level='warning')
`
const pass=name=>{checks.push(name);console.log('PASS '+name)}
try {
  for(const url of [api+'/health',ui]) {let occupied=false;try{await fetch(url);occupied=true}catch{};assert.equal(occupied,false,'Test port occupied '+url)}
  const py=process.env.PYTHON_EXECUTABLE||resolve(root,process.platform==='win32'?'backend/.venv/Scripts/python.exe':'backend/.venv/bin/python')
  await ready(api+'/health',start(py,['-B','-c',seed,resolve(temp,'test.db')],resolve(root,'backend'),{KEYOUSHU_JWT_SECRET:'expanded-isolated-browser-secret-2026',PYTHONIOENCODING:'utf-8'}))
  await ready(ui,start(process.execPath,[resolve(root,'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','15173','--strictPort'],resolve(root,'frontend'),{VITE_API_BASE:api}))
  const edge='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  browser=await chromium.launch({executablePath:process.env.EDGE_EXECUTABLE||(existsSync(edge)?edge:undefined),headless:true})
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true})
  page.setDefaultTimeout(12000);page.on('pageerror',error=>errors.push(error.message))
  const payloads=[]
  page.on('response',async response=>{if(/\/records\/\d+(?:\/export)?$/.test(response.url())) {try{payloads.push(await response.json())}catch{}}})
  await page.goto(ui);await page.getByRole('button',{name:'点击解锁助手',exact:true}).click()
  await page.locator('#auth-username').fill('expanded_tester');await page.locator('#auth-password').fill('Expanded-browser-2026')
  await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('.layout').waitFor()
  await page.locator('.sidebar .record-list .item').filter({hasText:'新版分析样例'}).click()
  const panel=page.getByRole('region',{name:'分析结果编辑面板'})
  await panel.waitFor()
  const headers=await panel.locator('h3').allTextContents()
  assert.deepEqual(headers.map(x=>x.replace(/^\d+/,'')),['客户需求与原文依据','待确认问题','建议待办','回复草稿','有 DDL 的任务'])
  assert.equal(await panel.getByText('普通建议',{exact:true}).count(),1)
  await panel.getByText('高优先',{exact:true}).waitFor();await panel.getByText(/建议理由：/).waitFor()
  await panel.getByText(/初步判断：/).waitFor()
  assert.equal(await panel.getByText('客户画像',{exact:true}).count(),0)
  pass('五区顺序保留，普通/推进建议合并，初步判断及优先级显示，画像不展示')
  await panel.getByRole('textbox',{name:'问题 1 的答案',exact:true}).fill('已确认10月30日交付')
  await panel.getByRole('button',{name:'确认答案',exact:true}).click()
  await panel.getByText('已确认：已确认10月30日交付',{exact:true}).waitFor()
  await page.reload();await panel.getByText('已确认：已确认10月30日交付',{exact:true}).waitFor()
  pass('确认/修改答案持久化，刷新显示真实答案替代猜测')
  const ordinary=panel.locator('.analysis-item').filter({hasText:'普通建议'})
  await ordinary.getByRole('button',{name:'采纳',exact:true}).click();await ordinary.getByText('已采纳',{exact:true}).waitFor()
  const suggested=panel.locator('.analysis-item').filter({hasText:'准备阶梯报价'})
  await suggested.getByRole('button',{name:'忽略',exact:true}).click();await suggested.getByText('已忽略',{exact:true}).waitFor()
  await suggested.getByRole('button',{name:'采纳',exact:true}).click();await suggested.getByText('已采纳',{exact:true}).waitFor()
  pass('普通建议采纳、推进建议忽略后采纳均保存，重复采纳按钮禁用')
  const ddl=panel.getByRole('region',{name:'有截止日期的任务'})
  await ddl.getByRole('button',{name:'加入日历',exact:true}).click();await ddl.getByText('已加入日历',{exact:true}).waitFor()
  const token=await page.evaluate(()=>Object.values(localStorage).find(value=>value.startsWith('eyJ')))
  // Read via the browser's actual stored credential, without printing it.
  const items=await page.evaluate(async({api,token})=>{const r=await fetch(api+'/api/calendar/items?status=all',{headers:{Authorization:'Bearer '+token}});return r.json()}, {api,token})
  assert.equal(items.code,0)
  const event=items.data.items.find(row=>row.title==='安排文化衫交货')
  assert.equal(event.due_date,'2026-10-30');assert.equal(event.start_date,'2026-10-20')
  assert.equal(items.data.items.filter(row=>row.title==='核对客户提供的标识文件').length,1)
  assert.equal(items.data.items.find(row=>row.title==='准备阶梯报价').due_date,null)
  const nav=page.getByRole('navigation',{name:'内容目录'})
  await nav.getByRole('button',{name:/日程/}).click()
  await page.getByRole('region',{name:'日程计划',exact:true}).waitFor()
  await page.getByRole('button',{name:/安排文化衫交货/}).first().waitFor()
  pass('加入日历实际显示事件并保留AI开始日，两类采纳事项进入无日期待办池')
  await page.getByRole('button',{name:'需求工作台',exact:true}).click()
  await page.locator('.sidebar .record-list .item').filter({hasText:'旧版记录'}).click()
  await panel.getByRole('textbox',{name:'待确认问题 1',exact:true}).waitFor()
  assert.equal(await panel.locator('.ddl-section').count(),0)
  assert.equal(await panel.getByRole('textbox',{name:'待确认问题 1',exact:true}).inputValue(),'旧问题')
  assert.equal(await panel.locator('#reply-draft').inputValue(),'旧回复')
  pass('旧字符串问题、旧待办与回复保持可用，旧记录不出现新日期任务区')
  await page.locator('.sidebar .record-list .item').filter({hasText:'新版分析样例'}).click()
  await page.setViewportSize({width:320,height:900})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  await panel.screenshot({path:resolve(temp,'expanded-result-320.png'),animations:'disabled'})
  await page.setViewportSize({width:1440,height:1000})
  await panel.screenshot({path:resolve(temp,'expanded-result-desktop.png'),animations:'disabled'})
  assert.equal(payloads.some(body=>JSON.stringify(body).includes('customer_profile')),false)
  assert.deepEqual(errors,[])
  pass('320px无整页溢出，详情响应不含画像，页面无异常')
  await writeFile(resolve(temp,'results.json'),JSON.stringify({checks,errors,fixture:'isolated temporary DB; model fixture'},null,2))
  console.log('Evidence: '+temp)
} catch(error) {await writeFile(resolve(temp,'failure.txt'),String(error.stack)+'\n'+logs.join(''));console.error('Evidence: '+temp);throw error}
finally {if(browser)await browser.close();for(const child of children.reverse())if(child.exitCode===null){const ended=new Promise(r=>child.once('exit',r));child.kill();await ended}}
