// Real browser/HTTP/storage, synthetic data only; cloud calls are trapped.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const root=fileURLToPath(new URL('../..',import.meta.url))
const require=createRequire(import.meta.url)
const {chromium}=require(process.env.PLAYWRIGHT_NODE_MODULES?resolve(process.env.PLAYWRIGHT_NODE_MODULES,'playwright'):'playwright')
const temp=await mkdtemp(resolve(tmpdir(),'keyoushu-speed-browser-'))
const api='http://127.0.0.1:18000',ui='http://127.0.0.1:15173'
const children=[],logs=[],checks=[],errors=[],latencies=[]
let browser
const pass=name=>{checks.push(name);console.log('PASS '+name)}
function start(command,args,cwd,env={}){
 const child=spawn(command,args,{cwd,env:{...process.env,...env},windowsHide:true,stdio:'pipe'})
 child.stdout.on('data',data=>logs.push(String(data)));child.stderr.on('data',data=>logs.push(String(data)))
 child.on('error',error=>logs.push(error.message));children.push(child);return child
}
async function ready(url,child){for(let n=0;n<100;n++){assert.equal(child.exitCode,null,logs.join(''));try{if((await fetch(url)).ok)return}catch{};await new Promise(r=>setTimeout(r,100))}throw new Error('Service unavailable '+logs.join(''))}
const seed=`
import sys
from pathlib import Path
import database
database.DB_PATH=Path(sys.argv[1]);database.init_db()
import auth_store
auth_store.create_user('speed_browser','Speed-browser-2026',['member'])
import ai_service,main,uvicorn
from fastapi import Depends
from auth import permission
cloud_calls=[]
def forbidden(*args,**kwargs):
 cloud_calls.append(1)
 raise ai_service.ModelAPIError('真实分析已进入；此隔离验收不调用云端')
ai_service.ChatCompletionsClient.complete=forbidden
@main.app.get('/test/cloud-count')
def count(user=Depends(permission('analysis:run'))):return {'count':len(cloud_calls)}
from fastapi.middleware.cors import CORSMiddleware
app=CORSMiddleware(main.app,allow_origins=['http://127.0.0.1:15173'],allow_methods=['*'],allow_headers=['*'])
uvicorn.run(app,host='127.0.0.1',port=18000,log_level='warning')
`
try{
 for(const url of [api+'/health',ui]){let occupied=false;try{await fetch(url);occupied=true}catch{};assert.equal(occupied,false,'Port occupied '+url)}
 const py=process.env.PYTHON_EXECUTABLE||resolve(root,process.platform==='win32'?'backend/.venv/Scripts/python.exe':'backend/.venv/bin/python')
 await ready(api+'/health',start(py,['-B','-c',seed,resolve(temp,'test.db')],resolve(root,'backend'),{KEYOUSHU_JWT_SECRET:'speed-browser-isolated-secret-2026'}))
 await ready(ui,start(process.execPath,[resolve(root,'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','15173','--strictPort'],resolve(root,'frontend'),{VITE_API_BASE:api}))
 const edge='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
 browser=await chromium.launch({executablePath:process.env.EDGE_EXECUTABLE||(existsSync(edge)?edge:undefined),headless:true})
 const page=await browser.newPage({viewport:{width:1440,height:1000}})
 page.setDefaultTimeout(12000);page.on('pageerror',error=>errors.push(error.message))
 await page.goto(ui);await page.getByRole('button',{name:'点击解锁助手',exact:true}).click()
 await page.locator('#auth-username').fill('speed_browser');await page.locator('#auth-password').fill('Speed-browser-2026')
 await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('.layout').waitFor()
 const submit=page.getByRole('button',{name:'开始分析',exact:true})
 const panel=page.getByRole('region',{name:'分析结果编辑面板'})
 await page.getByRole('button',{name:'填入演示样例',exact:true}).click()
 await page.locator('.chat-input').getByText(/演示结果：此固定样例/).waitFor()
 let begin=performance.now()
 await submit.click();await panel.locator('.sample-flag').getByText(/演示结果：/).waitFor()
 latencies.push({scenario:'text',submit_to_complete_ms:Math.round(performance.now()-begin)})
 await panel.getByText(/本次未调用云端分析/).waitFor()
 assert.equal(await panel.getByRole('region',{name:'有截止日期的任务'}).locator('.analysis-item').count()>0,true)
 pass('文字演示显示完整结果和显著演示标识，含客户需求、确认、建议、回复及日期任务')
 const ddl=panel.getByRole('region',{name:'有截止日期的任务'})
 await ddl.getByRole('button',{name:'加入日历',exact:true}).first().click()
 await ddl.getByText('已加入日历',{exact:true}).first().waitFor()
 await page.reload();await panel.locator('.sample-flag').waitFor();await ddl.getByText('已加入日历',{exact:true}).first().waitFor()
 pass('演示仍能加入日历、保存历史并在刷新后保留来源标识和已加入状态')
 await page.getByRole('button',{name:'填入截图样例',exact:true}).click()
 await page.locator('.chat-input img').waitFor()
 begin=performance.now()
 await submit.click();await panel.locator('.source-image img').waitFor({state:'attached'})
 await panel.locator('.sample-flag').waitFor()
 latencies.push({scenario:'image',submit_to_complete_ms:Math.round(performance.now()-begin)})
 await panel.locator('details.original > summary').click()
 await panel.locator('.source-image img').waitFor()
 pass('截图演示真实走图片上传与保存，完整结果无需云端，保留原图和核对转录')
 await panel.screenshot({path:resolve(temp,'demo-result.png'),animations:'disabled'})
 const token=await page.evaluate(()=>localStorage.getItem('keyoushu.auth.token'))
 const counts=await page.evaluate(async({api,token})=>{
  const headers={Authorization:'Bearer '+token}
  return {cloud:await(await fetch(api+'/test/cloud-count',{headers})).json(),customers:await(await fetch(api+'/api/customers',{headers})).json()}
 },{api,token})
 assert.equal(counts.cloud.count,0);assert.equal(counts.customers.data.total,0)
 pass('两种演示云端调用数均为0，虚构画像不混入我的客户')
 await page.getByRole('button',{name:'填入演示样例',exact:true}).click()
 await page.locator('#chat-text').fill((await page.locator('#chat-text').inputValue())+'\n客户：补充一条新要求。')
 await page.locator('.chat-input').getByText('样例内容已修改，将重新进行真实分析。',{exact:true}).waitFor()
 await submit.click();await page.getByText('真实分析已进入；此隔离验收不调用云端',{exact:true}).waitFor()
 assert.ok((await page.locator('#chat-text').inputValue()).includes('补充一条新要求'))
 const cloud=await page.evaluate(async({api,token})=>(await(await fetch(api+'/test/cloud-count',{headers:{Authorization:'Bearer '+token}})).json()).count,{api,token})
 assert.ok(cloud>0)
 pass('修改文字后进入真实分析，失败保留原文，不返回旧预置结果')
 await page.getByRole('button',{name:'填入演示样例',exact:true}).click()
 await page.locator('#customer-name').fill('新客户')
 await page.locator('.chat-input').getByText('样例内容已修改，将重新进行真实分析。',{exact:true}).waitFor()
 await page.setViewportSize({width:320,height:900})
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
 assert.deepEqual(errors,[])
 pass('修改客户名称取消演示标记，320px不溢出，浏览器无异常')
 await writeFile(resolve(temp,'results.json'),JSON.stringify({checks,errors,latencies,cloud:'trapped, no real service calls',fixture:'synthetic temporary database'},null,2))
 console.log(JSON.stringify({latencies,evidence:temp}))
}catch(error){await writeFile(resolve(temp,'failure.txt'),String(error.stack)+'\n'+logs.join(''));console.error('Evidence: '+temp);throw error}
finally{if(browser)await browser.close();for(const child of children.reverse())if(child.exitCode===null){const ended=new Promise(r=>child.once('exit',r));child.kill();await ended}}
