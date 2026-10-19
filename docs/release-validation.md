# 当前成果发布与复现验证

日期：2026-10-20（Asia/Shanghai）

## 发布对象

- 现有仓库：`philo-beep/chat-analysis`，默认分支 `main`。
- 发布包含登录注册、权限与后台统计、长样例、侧栏分类与聊天快捷目录、原文折叠、日历/待办池/甘特、历史建议自动同步、聊天删除确认及关联任务事务删除、云端文本/截图分析。
- 源码验证提交：`29a2135`。该文档提交仅补充验证记录，不改业务实现。

## 从空目录复现

在临时目录克隆已提交源码，创建全新 `backend/.venv`，按 README 执行 `pip install -r backend/requirements-dev.txt -c backend/constraints.txt` 与 `npm ci`；两者成功。没有复制原项目数据库、旧虚拟环境、依赖目录或原始压缩包。

验证环境：Windows，Python 3.14.7，Node.js 24.21.0，npm 11.19.0；未声称已验证其他操作系统或版本。

| 验证 | 结果 |
| --- | --- |
| 后端 unittest | 76/76 PASS，29.846 秒 |
| 真实 HTTP smoke | PASS：鉴权、分析替身、列表/详情、编辑/导出、图片及服务重启持久化 |
| 前端单元测试 | 13/13 PASS |
| 前端生产构建 | PASS |
| 日历隔离浏览器 | 13/13 PASS |
| 侧栏隔离浏览器 | 12/12 PASS |

HTTP 与浏览器回归使用隔离数据库和 AI 替身，不消耗云端额度；真实 AI 验证另见 `ai-module-acceptance.md`。本轮额外用真实模型验证明确 DDL 的文本和截图：均成功区分日历与无 DDL 待办池。

## 下载后仍需配置

1. 安装 README 中的 Python/Node 依赖，同时启动前后端。
2. 复制 `backend/.env.example` 为 `backend/.env`，填写用户自己的有效云端 API Key；服务、模型和推理强度按当前指定配置。
3. 注册新用户；管理员按 README 本机命令创建。新数据库在首次启动自动初始化，不包含原机器账号和聊天历史。
4. 浏览器测试默认使用 Windows Edge；没有 Edge 时安装 Playwright Chromium，详见 README。

## 发布边界

密钥、管理员密码、本机数据库、虚拟环境、node_modules、构建产物和原始压缩包均不提交。源码不依赖桌面模型目录。暂存区凭据扫描未发现本机 Key 或常见令牌/私钥模式。

推送前须重新拉取并确认无远端冲突；通过 PR 合入 main 后，再从 GitHub main 执行独立验收。验收结果与最终合并提交见交付汇报。
