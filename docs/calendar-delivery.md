# 日程计划交付与自验记录

交付日期：2026-10-19。运行入口：`http://127.0.0.1:5173/#/calendar`，甘特图为 `/#/calendar/gantt`。登录后在与历史记录同级的“日程计划”进入。前后端保持本机运行，本次未推送 GitHub。

## 已实现范围

- 月视图、开始日到 DDL 的逐日圆点、最多五点与超出数量、五级自动紧迫度、手动等级及恢复自动、独立逾期样式。
- 新建、编辑、删除和“完成任务”按钮。完成后立即停止日历与逾期提醒，保存实际完成时间，记录留在“已完成”中，支持重新打开。重复完成不会修改首次完成时间。
- 无 DDL 待办池；设 DDL 后转入日历。建议待办可从已保存的聊天导入，同一来源重复操作不会重复创建。
- 按钮或 G 切换月历／甘特图、日／周刻度、月内滚动、逾期虚线延伸、可选查看已完成灰色横条。编辑输入、弹窗打开时不会误触 G。
- 日历、等级、待办池、甘特图及事件操作的问号帮助，包含文字和步骤箭头。支持“知道了”、遮罩、Esc 关闭。
- 沿用 Vue 3、FastAPI、SQLite、现有请求和权限封装，未新增图库或依赖。界面使用真实接口；测试夹具仅在隔离临时数据库中使用。

## 日期与数据边界

只新增共享任务表 `task_items`，有无 DDL 使用同一表。字段及七类接口详见 [日程 API](calendar-api.md)。旧聊天表和历史记录行为保留；数据库启动时执行可重复的增量建表。

当前 AI 输出仍是 `tasks: string[]`，没有 `start_date`。开始日优先使用后端返回的 `start_date`，缺失时取 `created_at` 在 Asia/Shanghai 的日期；手动创建与建议导入当前均走创建日兜底。前端不猜测开始日，也不能向接口写开始日。此次没有变更分析接口契约或训练模型；未来若接入结构化 AI 日期，需要后端验证后写入该字段。

DDL 早于开始日时，不伪造开始日、不绘制反向区间：在 DDL 当天显示日期异常标记，并在逾期列表持续展示未完成任务。正常逾期甘特图保留开始日到 DDL 的计划段，再由 DDL 次日向今天画虚线延伸。

紧迫度依据 DDL 距今天的天数计算：≤2 天为 5 级，3–4 天为 4 级，5–6 天为 3 级，7–8 天为 2 级，≥9 天为 1 级。手动等级固定，逾期和完成状态优先决定显示样式。

## 七步操作验收

以下操作由真实浏览器、HTTP 接口、隔离 SQLite 自动执行，不向用户实际数据库写入样例。

| 操作 | 实际结果 |
|---|---|
| 1. 新增无 DDL 待办 | 保存后出现在待办池；数据库保存成功，开始日为创建日兜底。 |
| 2. 设三天后 DDL | 待办离开待办池；从创建日至 DDL 共四天均可打开同一事件，圆点为 4 级橙色 `#EA580C`。 |
| 3. 改手动 5 级 | 保存后为红色 `#DC2626`，后端记录 `manual_level=5`；恢复自动后变回空值。另有日期单元测试验证手动等级跨日期固定。 |
| 4. DDL 改昨天 | 立即变为深红逾期 `#7F1D1D`，显示反向日期异常标记，并出现在逾期列表。 |
| 5. 点击完成任务 | 圆点及逾期条目消失；完成时间持久化，已完成列表保留任务。后续重新打开可恢复提醒。 |
| 6. 按 G 切换 | 月历／甘特图双向切换、深链接刷新均正确；普通完成任务显示灰条，正常逾期任务显示虚线超时段。异常日期完成任务显示灰色异常标记。 |
| 7. 点击四处问号 | 均包含两段说明及步骤流程；按钮、遮罩、Esc 可关闭，帮助打开时 G 不切换。 |

附加检查：五点上限与 +n 完整列表、来源导入去重、用户隔离、只读权限、保存失败保留输入、390px 手机宽度无页面横向溢出。已检查桌面和手机截图。

## 测试结果与复现命令

- 后端：87 项通过。`backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v`
- 前端日期及目录：13 项通过。在 frontend 目录运行 `node --test tests/recordViews.test.mjs tests/calendarDates.test.mjs`。
- 前端构建：`npm run build` 通过。
- 日历浏览器：9 组通过。`node frontend/tests/calendar.browser.mjs`。
- 历史目录浏览器：11 组通过。`node frontend/tests/sidebar.browser.mjs`。覆盖长原文折叠、保存导出、快捷入口、深链接、账号隔离与失败重试。
- `git diff --check` 通过。本地健康检查返回 `status:ok`；前端 HTTP 200；未登录访问日历接口返回 401。

浏览器测试需 Playwright 和 Edge。当前工具位置通过环境变量 `PLAYWRIGHT_NODE_MODULES=C:\Users\pop\.codex\tools\keyoushu-browser\node_modules` 配置，没有写入项目依赖清单。

日历截图与结果：`C:\Users\pop\AppData\Local\Temp\keyoushu-calendar-GTeZOi`，包含 `results.json`、桌面／手机月历、桌面／手机甘特图以及四个帮助截图。

历史回归证据：`C:\Users\pop\AppData\Local\Temp\keyoushu-directory-5L36m5`。临时目录不是代码文件，系统清理后可用上述命令重新生成。浏览器验收不会调用真实 AI，不代表此次重新验证了模型提取质量。

## 文件清单

新增后端：`backend/calendar_store.py`、`backend/calendar_routes.py`、`backend/tests/test_calendar.py`。

后端接入：`backend/database.py` 增量建表、`backend/main.py` 注册路由、`backend/audit.py` 归类功能使用统计。

新增前端：`frontend/src/calendarDates.js`，以及 `frontend/src/components/` 下的 `CalendarPanel.vue`、`MonthCalendar.vue`、`GanttChart.vue`、`TodoPool.vue`、`EventDialog.vue`、`CalendarDialog.vue`、`HelpButton.vue`、`HelpDialog.vue`。

前端接入：`frontend/src/App.vue`、`api.js`、`navigation.js`、`recordViews.js`；组件 `AppIcon.vue`、`SidebarDirectories.vue`、`RecordContentList.vue`、`TaskList.vue`。

新增验证：`frontend/tests/calendarDates.test.mjs`、`frontend/tests/calendar.browser.mjs`；更新 `frontend/tests/recordViews.test.mjs`。

文档：`docs/calendar-api.md`、本文。未改动用户的 `更新功能/` 文件夹，未将数据库、凭证、测试产物纳入交付代码。

## 设计参考

参考 Google Calendar 官方任务说明中“明确标记完成、隐藏已完成任务、保留未完成任务供继续处理”的交互做法，只用于完善已获批的完成按钮、已完成列表和逾期展示，没有增加提醒通知、重复任务或外部日历同步。

官方说明：<https://support.google.com/calendar/answer/9901136?hl=en>（2026-10-19 查阅）。
