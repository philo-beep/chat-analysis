# 智能助手欢迎与登录界面交付

日期：2026-10-20。

## 用户路径与设计

匿名访问 → 动态客有数欢迎页 → 点击「点击解锁助手」→ 登录/注册 → 工作台。已登录会话刷新直接恢复工作台，未登录打开日历等深链接时保留目标页面。支持返回欢迎页；返回时清空密码并恢复解锁按钮焦点。退出及会话失效提示在欢迎页仍可见。

采用深墨绿、柔金、暖白的商务视觉。欢迎与登录背景呈现客户对话 → 需求整理 → 跟进待办的产品示意，均明确标注为示意内容。CSS 动效仅使用 transform 与 opacity，无外部字体、图片、动画库依赖。持续动画可以暂停/恢复，系统减少动态效果偏好下保持静态。手机卡片改为纵向排列，避免内容互相遮挡。

工作台延续品牌色、需求到行动的叙事与短暂入场动效，工作台动画结束后保持静止。

## 改动范围

- 新增 WelcomePanel.vue：欢迎页和解锁按钮。
- 新增 AssistantScene.vue：欢迎/登录共用的动态产品示意。
- LoginPanel.vue：内部控制欢迎/认证两层展示；保留既有认证 API、字段校验、用户名冲突提示。
- App.vue 与 style.css：工作台视觉与初次会话验证状态；补齐全局 canvas/soft 变量。
- 两组既有浏览器脚本增加解锁步骤；新增 entrance.browser.mjs 并接入 npm run test:browser。
- 无后端、数据库、AI 配置变动。

## 验收

| 检查 | 结果 |
| --- | --- |
| npm run build | PASS，55 个模块 |
| npm test | 13/13 PASS |
| calendar.browser.mjs | 13/13 PASS |
| sidebar.browser.mjs | 12/12 PASS |
| entrance.browser.mjs | 6/6 PASS |
| git diff --check | PASS |

入口验收覆盖：先欢迎后登录、动效暂停与恢复、键盘焦点、错误密码、密码规则提示、重复用户名、新用户注册登录、会话刷新、退出、390px/320px 无横向溢出、减少动画偏好、暂停状态下切换仍可见，以及登录后恢复日历深链接。原有两组回归覆盖保存导出、历史分类、账号隔离、任务完成、日历同步与删除联动。

测试使用临时 SQLite、合成账号和记录，不修改真实用户数据，不调用云端 AI。本轮不代表重新验收真实模型的文本/图片提取效果。

## 截图

- [欢迎页](evidence/assistant-entrance/welcome-desktop.png)
- [登录页](evidence/assistant-entrance/login-desktop.png)
- [工作台](evidence/assistant-entrance/workspace-desktop.png)
- [320px 欢迎页](evidence/assistant-entrance/welcome-320.png)
- [320px 登录页](evidence/assistant-entrance/login-320.png)
- [320px 注册页](evidence/assistant-entrance/register-320.png)

本地访问：http://127.0.0.1:5173/ 。已登录用户会自动进入工作台；退出登录后可查看完整欢迎与登录流程。
