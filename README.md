# 面向小微商家的 AI 客户需求整理与跟进助手

输入一段聊天原文，输出结构化结果：**需求**、**待确认问题**、**建议待办**、**回复草稿**。

2026-10-20 扩展分析：保留上述功能，增加有截止日期的任务、带理由和优先级的推进建议；推进建议与普通建议合并显示。新记录需点击“采纳”进入待办池、“加入日历”建立排期；旧记录原有同步行为保留。问题支持初步判断与人工确认。客户画像只由后端保存，前端和导出不返回画像。详见 [扩展交付与实际验收](docs/expanded-ai-delivery.md)，包括真实长对话尚未通过的限制。

当前版本包含登录注册与权限校验、文本/截图聊天分析、历史记录与内容目录、原文折叠、编辑导出、个人日历/待办池/甘特图，以及聊天删除与关联日历任务联动。完整运行需要后端与前端同时启动，并配置有调用权限的云端 AI Key。

GitHub 默认 `main` 分支为完整交付版本。运行代码已在仓库中，不需要原始压缩包或桌面模型目录；用户数据和凭据需要在新机器上重新建立。

## 目录结构

```
项目/
├─ frontend/                 前端
│  └─ src/
│     ├─ App.vue             页面总入口，A 负责
│     ├─ components/
│     │  ├─ ChatInput.vue    聊天输入，A 负责
│     │  ├─ RecordList.vue   历史列表，A 负责
│     │  └─ ResultPanel.vue  结果与编辑，B 负责
│     └─ api.js              前端请求封装，A 负责
├─ backend/                  后端
│  ├─ main.py                接口入口，C 负责
│  ├─ database.py            数据保存，C 负责
│  └─ ai_service.py          AI 调用与结果处理，D 负责
├─ samples/                  演示与测试样例，E 负责
├─ docs/
│  ├─ api.md                 接口约定，C 维护
│  ├─ acceptance.md          验收清单，E 维护
│  ├─ tasks.md               任务看板（按人分工，全组维护）
│  ├─ workflow.md            日常协作操作手册（每人每天都看这个）
│  └─ github.md              克隆、上传与代理配置
└─ README.md                 启动与使用说明
```

除了上面这些，还有几个让项目能真正跑起来的文件：`frontend/index.html`、`package.json`、
`vite.config.js`、`src/main.js`，以及 `backend/requirements.txt`、`.env.example`，
还有根目录的 `.gitignore`、`.gitattributes`。

## 环境准备与启动

已验证环境：Windows、Python 3.14.7、Node.js 24.21.0（npm 11.19.0）。以下命令使用 PowerShell；macOS/Linux 的虚拟环境 Python 路径改为 `backend/.venv/bin/python`。首次安装需要联网。

### 下载与配置

```powershell
git clone https://github.com/philo-beep/chat-analysis.git
cd chat-analysis
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -c backend/constraints.txt
Copy-Item backend/.env.example backend/.env
notepad backend/.env
```

在本机 `backend/.env` 填写 `FOLLOWUP_API_KEY`。模板已给出当前服务地址、模型 `gpt-6.1-sol` 和推理强度 `medium`。需要该服务有效凭据和模型调用权限；仓库不附带共享密钥。没有配置 Key 时，登录、历史和日历仍可使用，实际 AI 分析会失败并提示重试。

### 后端（第一个终端）

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

后端地址：http://127.0.0.1:8000 ，接口文档：http://127.0.0.1:8000/docs

首次运行后可在前端注册普通成员。管理员只能由本机命令或已有管理员创建：

```powershell
cd backend
.\.venv\Scripts\python.exe manage_users.py --bootstrap-admins
```

该命令一次性创建两个不同随机密码的管理员，密码仅写入当前用户的
`~/.codex/local-credentials/keyoushu-admins.txt`，不会打印到终端或提交 Git。
若账号或凭据文件已存在，整批取消，避免覆盖。登录后点击“后台统计”查看访问与功能使用情况。
所有分析/记录接口现均需 Bearer token；普通成员只能访问自己的记录，旧记录仅管理员可见。
部署、接口、数据迁移和验证详见 [访问控制说明](docs/access-control.md)。

### 前端

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

前端地址：http://127.0.0.1:5173

### 配置

当前版本按用户指定使用云端模型。旧的本地 NB/Qwen 说明及历史报告仅记录早期版本，不是当前运行依赖。

文本分析与聊天截图转录使用已接入仓库源码的云端 AI 服务。请在被 Git 忽略的 `backend/.env` 中配置 `FOLLOWUP_API_KEY`、`FOLLOWUP_BASE_URL`、`FOLLOWUP_MODEL` 和 `FOLLOWUP_REASONING_EFFORT`；当前模型按用户指定为 `gpt-6.1-sol`，推理强度为 `medium`。修改配置后重启后端。

截图先逐字转录，再进行结构化分析；页面保留原图和转录供核对。默认开启同模型质量复核，文本分析有两次模型请求，截图分析有三次，实际等待时间取决于供应商响应。AI 调用失败会提示重试，不用假数据替代。配置说明见 [docs/local-model.md](docs/local-model.md)。

**密钥和本地数据库不提交到仓库**，配置模板可以共享。

### 后端回归验证（C）

在项目根目录执行；建议使用单独虚拟环境，避免影响其他项目：

```powershell
python -m venv .venv-c
.\.venv-c\Scripts\python.exe -m pip install -r backend/requirements-dev.txt -c backend/constraints.txt
.\.venv-c\Scripts\python.exe -B -m unittest discover -s backend/tests -v
.\.venv-c\Scripts\python.exe -B backend/tests/smoke_http.py
```

测试使用临时 SQLite 文件，验证六个接口、逐条消息、截图上传、中文导出、兼容迁移、跨进程读取、非法数据和错误返回，不修改 `backend/app.db`。
`smoke_http.py` 会在随机本机端口启动真实 Uvicorn，执行完整 HTTP 链路，重启服务并复查已保存修改，结束后自动停止测试服务。
单元测试和 HTTP smoke 均显式注入模型替身，与 D 的模型运行模式隔离；它们验证接口边界，不代表真实 AI 测试样例通过。HTTP 测试另外验证截图 multipart 请求与原图、转录的服务重启持久化。
启动服务后可访问 `/health`、`/docs` 检查状态。模型错误、数据库错误和历史记录损坏会在后端日志中区分记录，具体返回和保存示例见 `docs/api.md`。

前端已接入编辑保存、历史和服务端导出。真实业务分析由 D 维护，所有代码合并后由 E 执行文档中的文本、截图和浏览器完整流程验收。

真实模型验收（使用临时数据库，`--images` 会实际调用已配置的云端模型并消耗供应商额度，不注入模型替身）：

```powershell
backend/.venv/Scripts/python.exe -B backend/tests/check_acceptance.py --images --output "$env:TEMP/keyoushu-acceptance.json"
```

前端验证在 `frontend` 目录执行 `npm test`、`npm run build`。浏览器验收执行 `npm run test:browser`，四组测试（日历、侧栏、欢迎与登录、扩展分析操作）顺序运行，使用临时数据库及端口 18000/15173，不调用云端 AI。Windows 默认使用已安装的 Edge；无 Edge 时先执行 `npx playwright install chromium` 下载测试浏览器。可用 `EDGE_EXECUTABLE` 指定浏览器路径、`PYTHON_EXECUTABLE` 指定后端 Python；不需要本机 Codex 工具目录。

输入和合成截图位于 `samples/acceptance-cases.json` 与 `samples/screenshots/`；检查结果与实际转录写入指定 JSON，任一检查失败时退出码为 1。

### 输入与记录

`POST /analyze` 支持 JSON `text` 或 `messages`（二选一），截图使用 multipart `text` + `image`。PNG、JPEG、WebP 图片最大 10 MiB；后端会检查真实文件内容和像素数。
原始文字、逐条消息和上传图片均可核对：详情/导出包含原始输入 `source_input`、原图 `source_image` 和截图转录 `source_transcript`。SQLite 启动迁移保留旧记录。完整输入和错误约定见 [docs/api.md](docs/api.md)。

工作台提供文字演示样例（`Ctrl/Cmd + Shift + D`）和买卖双方聊天截图演示样例，方便体验文字与图片整理流程；截图为虚构对话，不含真实客户资料。

## 数据约定

接口：`POST /analyze`，输入聊天原文，输出固定字段的 JSON。详见 [docs/api.md](docs/api.md)。

字段名称、数据类型和空值规则**必须固定**，前后端才能同时开工。

## 分工与文件负责人

| 文件 | 负责人 |
| --- | --- |
| frontend/src/App.vue | A |
| frontend/src/components/ChatInput.vue | A |
| frontend/src/components/RecordList.vue | A |
| frontend/src/api.js | A |
| frontend/src/components/ResultPanel.vue | B |
| backend/main.py | C |
| backend/database.py | C |
| backend/ai_service.py | D |
| samples/ | E |
| docs/api.md（维护） | C |
| docs/acceptance.md（维护） | E |

需要改别人负责的公共文件时，先在群里说明，减少同时修改造成的冲突。

## 分支与合并规则

每天的具体操作步骤（含每条命令会产生什么结果）见 [docs/workflow.md](docs/workflow.md)。

| 分支 | 用途 |
| --- | --- |
| main | 当前能够运行的共同版本 |
| codex/input-history | A 的功能分支 |
| codex/result-panel | B 的功能分支 |
| codex/backend | C 的功能分支 |
| codex/ai-analysis | D 的功能分支 |
| codex/test-demo | E 的功能分支 |

每个人的工作循环：

1. 切到自己的功能分支，并把最新的 `main` 合并进来（分支已经建好了，不用自己创建）。
2. 修改负责的文件，在本机运行检查。
3. 提交并上传代码。
4. 发起合并请求（PR），说明做了什么、怎么验证。
5. 相关文件的负责人检查；通过的 PR 由 C 合并到 `main`，C 自己的改动由另一名技术成员合并。
6. 合并后，大家同步最新代码，重新运行。

一个 PR 只处理一件相对完整的事情，附上操作截图及验证步骤。合并后要**实际运行一次**：代码没有文字冲突，不代表组合起来就能正常工作。

## 联调检查点

三个检查点分别要完成什么、出问题优先找谁，见 [docs/acceptance.md](docs/acceptance.md)。
进度在 [docs/tasks.md](docs/tasks.md) 里更新。

问题反馈格式：**输入内容、操作步骤、实际结果、预期结果**（附截图）。

## 上传到 GitHub

- 每天的提交、上传、发 PR：[docs/workflow.md](docs/workflow.md)
- 克隆、连不上 GitHub 怎么办：[docs/github.md](docs/github.md)
