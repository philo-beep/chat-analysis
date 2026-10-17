# C 后端交付与运行记录（2026-10-18）

## 范围与冲突处理

从本地 main 的 106f47d 创建 codex/backend，合并既有远端 origin/codex/backend 的 d0f493e。
远端增加逐条 messages 输入，本地已有严格结构校验、错误处理和来源保护，两者在 main.py、docs/api.md 冲突。
用户确认方案 3 后逐项整合，保留两边功能；未使用覆盖、强制推送或新建远端仓库。

## 已完成

- 六个接口路径和 /analyze 六个响应字段不变。
- JSON 保留 text、messages 二选一；保留姓名、角色、时间和字段别名，转交 D 时明确客户/商家角色，另外持久化原始 JSON。
- 新增 multipart text + image，支持纯截图。PNG/JPEG/WebP 最大 10 MiB、2500 万像素；检查真实图片格式、完整解码、MIME、空文件、重复字段和总请求大小。
- 图片调用内部 analyze_chat_with_source(text, image_bytes, image_mime)，返回 ai_contract.AnalysisOutcome(result, source_text)；文本仍只调用一次 analyze_chat(str)，与已有调用兼容。
- 原图 data URL、原始输入、截图角色转录一并保留；record.text 合并原始文字和截图转录，真实结果的 evidence 必须能在其中找到。
- SQLite 启动迁移增加 source_input、source_image、source_transcript，保留旧记录；历史列表不携带原图。
- 保留严格结果校验、编号保护、is_sample 服务端来源保护、中文导出、事务回滚、连接关闭和友好错误；失败不创建记录。
- 模型工作在线程池中执行，文本/截图失败都能返回可重试提示。D 的调用应自行设置本地模型超时，不少于 180 秒以覆盖首次加载。
- 更新接口文档、启动说明和测试；未修改 ai_service.py 的 D 业务实现。

## 实测结果

Windows，Python 3.14.7。执行依赖安装：

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
```

当前安装 FastAPI 0.143.3、Starlette 1.8.0、Pydantic 2.14.1、python-multipart 0.0.32、Pillow 13.0.0、httpx 0.28.1。
Starlette 对 httpx 测试后端给出弃用提示，现有组合仍可运行。只安装运行依赖的环境须先安装 requirements-dev.txt 才能运行测试。

### 回归：32 项全部通过

```powershell
backend/.venv/Scripts/python.exe -B -m unittest discover -s backend/tests -v
```

原 24 项回归全部保留，新增消息角色/时间/原始输入、无效消息、图片透传/保存/导出、纯图片 JPEG/WebP、伪造/损坏/超限图片、截图模型失败/错误引用、不合法请求和旧库迁移等检查。
也在仓库外的 keyoushu-c-review-venv 验证通过。

修复测试自身的 Windows 资源问题：迁移测试通过 closing() 显式关闭 SQLite 连接，避免 with sqlite3.connect() 仅提交事务而不关闭连接造成临时文件占用。

### 真实 HTTP 与重启：通过

```powershell
backend/.venv/Scripts/python.exe -B backend/tests/smoke_http.py
```

脚本启动真实 Uvicorn，在随机端口执行分析、历史、详情、修改、导出及错误请求，额外执行 messages 与 multipart 图片上传。
停止并重启服务后，人工修改、来源标记、原图和转录保持一致。
测试进程通过管道收集日志并 communicate() 清理，避免 Windows 继承具名日志句柄导致临时目录无法删除。

全部测试使用临时 SQLite，不修改 backend/app.db；测试结束自动停止服务。
git diff --check 通过，两个冲突文件均无冲突标记。

## 边界和待办

- 单元测试和真实 HTTP smoke **显式注入模型替身**，证明接口和持久化链路，不证明真实 AI 业务质量。
- D 继续接入用户桌面的 ai_followup_trainer 文本模型、本地 Qwen 截图模型和项目适配；C 图片桥接会在 D 未实现时友好报错，不回退开发样例。
- E 在全部分支合并后执行五组真实文本/截图样例、角色识别和浏览器完整验收。
- 本次按用户流程完成本地提交，**尚未 push**；后续由总控 pull、审查、自检并取得用户确认后推送。
- 未纳入 .obsidian/workspace.json 或总控负责的 Git 工作流文档。
