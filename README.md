# 面向小微商家的 AI 客户需求整理与跟进助手

输入一段聊天原文，输出结构化结果：**需求**、**待确认问题**、**建议待办**、**回复草稿**。

本项目由一个共享代码仓库承载，每人负责一块，每天多次合并验证。

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

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

后端地址：http://127.0.0.1:8000 ，接口文档：http://127.0.0.1:8000/docs

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端地址：http://127.0.0.1:5173

### 配置

复制 `backend/.env.example` 为 `backend/.env`，填入自己的密钥。

**密钥和本地数据库不提交到仓库**，配置模板可以共享。

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
