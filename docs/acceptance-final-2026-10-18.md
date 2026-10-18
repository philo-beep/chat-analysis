# 客有数最终验收报告

日期：2026-10-18  
验收角色：独立 Agent E  运行仓库：`main` @ `6f4788c07fb42992f3fcf394700a3bb9ebde646a`  
验收克隆：`C:/Users/pop/AppData/Local/Temp/keyoushu-e-final`  
分支：`codex/test-demo`

## 结论与口径

本次独立验收覆盖 10 项文档验收标准、6 组真实文本、6 组真实截图、后端回归、真实 HTTP/重启、前端构建和 Edge 浏览器完整链路。按本次桌面 MVP 验收范围，文档 10 项为 10/10（100%）；这不表示现实聊天类型全覆盖、跨机器启动完成或生产环境完成。真实模型结果 12/12 通过，后端 unittest 63/63 通过；浏览器脚本记录的主流程事件为 12/12，拆分为功能断言 10/10、无 pageerror 质量检查 1 项和手机宽度测量 1 项。手机测量只作为风险记录，不计入功能通过数。未发现桌面 MVP 阻塞缺陷。

文本使用仓库内复制的 `ai_followup_trainer` 字符 n-gram NB 模型与项目适配规则；复制权重 SHA-256 与桌面来源一致：`8ec5c3a4f8ef925f35028102bb2ca2f7f5c33ea0708d9f9861c1443b8bd5ae87`。截图使用本机 Ollama `qwen2.5vl:7b` 转录，再进入同一文本分析管道。没有执行 LoRA 或 Qwen 权重训练，结果均按真实模型标记 `is_sample=false`。

总控已报告正式默认端口 `8000/5173` 的网站启动、`GET /health` 和 Edge 打开均通过；本次 E 自己使用临时端口 `18000/15173`，并在测试启动包装器中额外允许 `15173` CORS。业务 `main.py` 的正式 CORS 白名单只包含 `5173`，因此自定义端口的初次 OPTIONS 400 是测试配置限制，不列为业务缺陷（初始证据见 `docs/evidence/final-browser-initial-cors-failure.json`）。异机启动、会议和邀请没有验证证据，不宣称完成。

## 10 项结果

| 项目 | 结果 | 证据 |
|---|---|---|
| 空输入提示补充内容 | 通过 | 浏览器 `empty input validation`；`final-browser-empty.png` |
| 分析加载提示 | 通过 | 浏览器文本/图片流程；`final-browser-image-loading.png` |
| 数量、预算等事实与原文一致 | 通过 | 6 文本 + 6 图片均 `grounded_evidence=true` |
| 未提供信息进入待确认 | 通过 | `missing`、`normal`、`approximate`、`roles` 结果 |
| 待办与客户事实分离 | 通过 | `roles` 的商家“初步方案”未进入 requirements |
| evidence 可在原文找到 | 通过 | 12 组 `grounded_evidence=true` |
| 修改保存后刷新一致 | 通过 | 文本和图片编辑、重启回读；浏览器导出证据 |
| 历史记录打开 | 通过 | 历史列表、记录切换、刷新恢复 |
| 复制和导出完整 | 通过 | 剪贴板断言、文本/图片 JSON 导出 |
| 模型失败提示并可重试 | 通过 | 缺失模型注入显示错误；恢复后同输入重试成功 |

## 12 组真实模型实测

脚本：`backend/tests/check_acceptance.py --images --output docs/evidence/final-real-acceptance.json`。文本耗时约 `0.01-0.02s`；图片耗时约 `2.82-12.18s`，首次调用最慢约 `12.18s`。全部记录 `status=200`、`is_sample=false`、evidence 可回溯；图片全部保存 `source_image` 和非空 `source_transcript`。

| 场景 | 文本 | 图片 | 关键检查 |
|---|---:|---:|---|
| 正常询价 | 通过 | 通过 | 100件、3000元、10月30日前、设计；追问年份/尺码 |
| 信息不足 | 通过 | 通过 | 无数字事实；追问数量、预算、时间 |
| 明确修改 | 通过 | 通过 | 最终 150 件；evidence 为修改原文 |
| 表达模糊 | 通过 | 通过 | 约100件、3000-4000元；时间待确认 |
| 信息矛盾 | 通过 | 通过 | 3000/5000 预算保持歧义并追问 |
| 甲乙角色/单价 | 通过 | 通过 | 150件、纯棉、40元左右/件、下周；商家方案不作客户事实 |

## 浏览器完整链路

可重跑脚本：`docs/evidence/final-browser-check.mjs`。使用 Edge headless、临时 SQLite、后端 `18000`、Vite `15173`，结束自动停止测试进程。

已实测：

1. 空提交提示；快捷键填充演示文本；真实文本分析返回 `is_sample=false`。
2. 编辑数量和回复，保存、刷新、历史重开；复制回复内容与编辑后文本一致。
3. 导出前自动保存；文本与图片 JSON 均包含 result、原文、记录元数据，图片还包含完整 `source_image` 和 `source_transcript`。
4. 注入不存在的 NB 模型路径，页面显示“模型调用失败，请稍后重试”，输入保留；恢复配置后同输入重试成功。
5. 停止后端，页面显示“无法连接后端服务”；恢复后继续操作。
6. 注入真实 422（`text` 数字）和历史列表 500，分别显示字段错误和历史错误，恢复后独立消失。
7. 上传 `roles.png`，等待期间控件禁用；真实 Qwen 返回后原图、转录、甲乙角色和 150 件结果可见。
8. 重启后端，图片记录和编辑仍在；切换文字历史时旧图片被清除；再次打开图片记录可导出。
9. UI-only 注入 `is_sample=true` 验证开发样例显著提示；不将其计入真实模型通过。
10. Edge 无 `pageerror`。

证据：`final-browser-results.json`、`final-browser-run.txt`、`final-browser-*.png`、`final-browser-*-export.json`、`final-browser-image-record.json`。

## 回归、部署与环境

- `unittest discover -s backend/tests -v`：63/63 通过。
- `backend/tests/smoke_http.py`：真实 Uvicorn、health/analyze/list/detail/edit/export、UTF-8、400/404/422、messages、multipart 图片、进程重启全部通过；仅临时数据库。
- `npm ci --offline --no-audit --no-fund`：通过；安装 31 packages。
- `npm run build`：Vite 5.4.21 构建通过。
- `pip check`：No broken requirements found。
- 运行时：Python 3.14.7、FastAPI 0.143.3、Uvicorn 0.54.0、Pydantic 2.14.1、Pillow 13.0.0、httpx 0.28.1。
- 正式默认端口 `8000/5173`：按总控提供的运行证据，健康检查和 Edge 打开通过；E 未接管或停止这些服务。
- E 临时端口 `18000/15173`：验收结束已停止；Ollama `11434` 保持运行。

## 问题 001

状态：已验证不复现。  
输入：`数量改成150件，其他要求后面再说。`  
实际：真实文本和截图均最终输出 `数量=150件`，evidence 指向修改原文。  
预期：显示最终数量 150 件并保留依据。  
负责人：D/C；结论：关闭。

## 遗留风险与边界

| 优先级 | 项目 | 影响/边界 |
|---|---|---|
| P2 | 390px 手机视口存在横向溢出 | 浏览器实测 `innerWidth=390`、`scrollWidth=732`；桌面 MVP 可用，移动适配留后续处理 |
| P2 | Qwen 截图识别依赖本机 Ollama 与模型 | 实测图片耗时 2.82-12.18s；需人工核对原图、转录和 evidence，不能保证所有真实截图无识别错误 |
| P2 | 多进程视觉并发未验证 | 当前实现按单 worker/进程内锁设计，生产扩展需另行验证 |
| P3 | 正式 CORS 仅允许 5173 | 默认端口通过；使用自定义前端端口需配置白名单，E 已在临时启动器中处理 15173 |
| P3 | 异机启动未验证 | 没有第二台机器或会议/邀请证据，不宣称 README 跨机器通过 |

## 下一步建议（按顺序）

1. 扩充真实截图样本，覆盖不同聊天应用、分辨率、字体、气泡布局和角色标注，并逐张人工核对 Qwen 转录与 evidence。
2. 处理 390px 手机视口的横向溢出，重新执行手机截图和交互回归。
3. 将前端自定义端口加入可配置 CORS 白名单，或在部署时固定前端端口；再验证非默认端口的真实部署。
4. 在另一台干净机器按 README 完整启动并记录证据，补做异机安装、Ollama 模型准备与导出检查。
5. 对多进程/并发截图请求做队列和超时压测，再评估生产部署边界。

## 代码路径证据

- `backend/ai_service.py:35-48`：运行时读取本地 NB 模型；`58-100`：本机 Ollama 校验、无代理、无云模型、转录。
- `backend/main.py:266-342`：图片格式/像素校验、真实模型调用、source_image/source_transcript 持久化、evidence 校验。
- `backend/main.py:398-437`：历史读取、编辑保留 `is_sample`、完整导出。
- `backend/database.py:32-110`：SQLite 迁移、原始输入/图片/转录保存和读取。
- `frontend/src/App.vue:38-63`：分析、详情读取、错误提示、重试后状态处理。
- `frontend/src/components/ResultPanel.vue:45-106`：保存、复制、导出前自动保存。
- `frontend/src/components/ChatInput.vue:18-79`：文本、图片、粘贴、演示快捷键和空输入校验。

## 范围取舍

本次不实现微信接入、语音识别、自动发消息、复杂账号权限；不把本地模型适配称作 LoRA 微调；不把合成截图当作用户真实聊天；不声称异机启动或会议邀请完成。
