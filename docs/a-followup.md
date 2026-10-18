# A 前端联调修正报告

日期：2026-10-18。工作树：`keyoushu-a-followup`，分支：`codex/input-history`。

## 改动

- `frontend/src/api.js`：FastAPI `detail` 数组按字段路径展示；常见缺失、文字类型、列表、长度等错误使用中文提示，不显示原始对象。字符串业务错误继续直接显示。
- `frontend/src/App.vue`：历史列表错误单独保存，仅在历史栏显示。刷新历史清理自己的错误，不清除分析失败或记录打开失败。打开失败提示记录编号和服务端原因。
- `frontend/src/components/ChatInput.vue`：只允许 PNG、JPEG、WebP；无 MIME 时按这三类扩展名初筛，实际图片字节仍由后端验真；上限保持 10 MiB。保留客户名称、全部原文、粘贴、预览、快捷键及 `text/image` 契约。

## 验证结果

`npm ci --offline --ignore-scripts --no-audit --no-fund`、`npm run build`、`git diff --check` 均通过。

使用系统 Edge 无头浏览器访问本工作树 Vite 服务，实际操作页面。网络层用 Playwright 返回指定接口响应，检查真实页面和实际发出的请求；未替代组件实现。

| 检查 | 结果 |
| --- | --- |
| 422 两个字段错误显示中文字段路径、缺失或类型原因 | 通过 |
| JSON 请求保留客户名元信息、原文空格与换行 | 通过 |
| 历史失败仅在历史栏；刷新成功清除自己的错误、保留分析错误 | 通过 |
| 模型 500 字符串提示；原样重试后成功，旧错误消失 | 通过 |
| 模拟延迟期间加载状态和输入禁用，完成后恢复 | 通过 |
| 缺失记录显示编号和“记录不存在”；刷新历史不清除此错误 | 通过 |
| 重新打开成功及页面刷新恢复记录和完整原文 | 通过 |
| GIF/SVG 拒绝；PNG/JPEG/WebP 可选并预览；超过 10 MiB 拒绝 | 通过 |
| 纯图片提交保留 multipart 的 text/image 字段及浏览器生成的 boundary | 通过 |
| 只填客户名不分析；全局 Ctrl+Shift+D 填充角色样例及客户名 | 通过 |

浏览器检查脚本位于本机临时目录 `C:/Users/pop/AppData/Local/Temp/keyoushu-browser-check/a-followup-check.mjs`。测试结束后关闭临时浏览器和 Vite 服务。

本次未验证真实模型效果、真实图片解码、40–120 秒模型耗时或远端验收；图片测试仅验证前端格式与请求边界。未改 ResultPanel、后端或任务看板。按本轮要求仅本地提交，未推送。
