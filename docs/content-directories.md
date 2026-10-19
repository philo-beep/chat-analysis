# 内容目录与原文折叠

保留原历史记录列表，在同级增加建议待办、待确认事项、聊天截图。
工作台原文默认折叠，点击可展开和收起；展开后的完整内容在限定高度内滚动。
切换记录或账号时恢复折叠。切换目录保留工作台未保存的草稿；打开不同来源记录前仍需先保存。

## 导航地址

沿用 Vue `section` 切换，不安装路由库，以 hash 同步地址和选中态。

| 地址 | 内容 | 权限 |
| --- | --- | --- |
| `/` 或 `/#/` | 需求工作台及原历史记录 | 登录 |
| `/#/tasks` | 建议待办 | 登录，服务端 `records:read` |
| `/#/questions` | 待确认事项 | 登录，服务端 `records:read` |
| `/#/screenshots` | 聊天截图 | 登录，服务端 `records:read` |
| `/#/admin` | 原网站后台统计 | `admin:stats`，接口再次校验 |

三个目录均支持刷新后恢复选中态、浏览器前进后退，以及点击条目打开来源记录。
没有接口占位或假数据。普通成员与管理员的数据范围继续由现有后端权限决定。

## 数据与限制

- `GET /records` 返回最近 100 条可访问记录的摘要；逐条通过 `GET /records/{id}` 获取详情。
- 从已保存的 `result.tasks` / `result.questions` 展开列表，排除空白字符串，保留来源与数组位置，不跨记录去重。
- `source_image` 非空的记录显示于聊天截图。转录仅展示前 240 字摘要，来源记录保留完整内容。
- 详情最多 3 个并发，按更新时间缓存于当前页面会话。刷新重新取数；切换账号清空缓存，迟到响应不得写回新账号。
- 单条失败显示来源编号和错误，保留其他成功结果；整体列表失败显示错误，不伪装成空状态。
- 数量仅代表最近 100 条范围。读取较多截图时仍有传输成本，后续可增加轻量分类接口与分页。
- 没有新增后端接口或数据库字段。未实现完成状态、负责人、截止时间、问题解决状态、收藏或客户分类，这些需要后端补充业务模型。

## 文件范围

修改 `frontend/src/App.vue`（目录挂载、导航和数据协调）、
`frontend/src/components/ResultPanel.vue`（原文折叠）。

新增：

- `frontend/src/navigation.js`、`frontend/src/recordViews.js`。
- `frontend/src/components/SidebarDirectories.vue`、`RecordContentList.vue`。
- `frontend/src/components/TaskList.vue`、`QuestionList.vue`、`ScreenshotList.vue`。
- `frontend/tests/recordViews.test.mjs`、`frontend/tests/sidebar.browser.mjs`。
- 本说明文件。

原 `RecordList.vue`、鉴权封装、后端和模型模块未修改。

## 验证

在项目根目录执行：

```powershell
node --test frontend/tests/recordViews.test.mjs
```

在 `frontend` 下执行 `npm run build`。

浏览器回归要求本机有 Playwright 测试工具、Edge、后端虚拟环境，以及空闲的 18000/15173 端口。
Playwright 安装在项目外；不加入应用依赖。设置 `PLAYWRIGHT_NODE_MODULES` 指向其 `node_modules`，例如本机：

```powershell
$env:PLAYWRIGHT_NODE_MODULES = "$env:USERPROFILE/.codex/tools/keyoushu-browser/node_modules"
node frontend/tests/sidebar.browser.mjs
```

可选 `PYTHON_EXECUTABLE` / `EDGE_EXECUTABLE` 指定运行程序。
测试创建临时 SQLite，启动真实后端和前端，结束自动停止测试服务，不触碰用户 `backend/app.db`。
截图与结果写入终端输出的系统临时目录。测试使用合成记录，不代表重新验收模型识别效果。

已通过 5 项数据与导航测试、8 组浏览器流程：长原文折叠与完整滚动、分类/来源跳转/草稿保留、保存导出及更新同步、
三个目录刷新选中态及浏览器返回、窄屏、账号隔离与全部空状态、部分失败恢复、列表失败恢复。
