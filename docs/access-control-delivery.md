# 访问控制交付记录（2026-10-19）

## 完成范围

已实现注册、登录、当前用户、注销、可撤销JWT、Argon2id密码、RBAC五表、记录归属隔离、
管理员访问与功能统计、简单登录注册界面、后台统计页面、两个本机管理员。
本次明确接入A的App.vue/api.js；B结果面板仅改鉴权导出、复制事件上报、卸载时迟到操作保护。
没有修改D的模型或推理规则。用户后续要求“注册”覆盖原分工文档排除注册的限制。

## GitHub兼容情况

仓库为 `philo-beep/chat-analysis`，继续使用已有仓库。
开发前已拉取远端，并将队友 B 的 `e758654`（会话保护）快进合入 `codex/access-control`。
该提交基于 main 的 `5285495`（长对话样例PR #7）。保留B的会话参数与迟到响应保护。
提交后按工作流再次pull main；首次推送前须得到用户针对本次提交的明确批准。
本记录不表示已推送，也不表示已合并main。

## 验证结果

| 验证 | 结果 |
| --- | --- |
| unittest discover | 78项全部通过，11.224秒 |
| 真实Uvicorn HTTP smoke | 登录、分析、编辑、导出、重启后持久化全部通过 |
| 实际本地文本模型 | 6/6样例通过 |
| 实际本机Qwen截图模型 | 6/6通过，首例12.13秒，其余2.21–3.42秒 |
| Vue生产构建 | 通过，25 modules |
| Edge无头浏览器真实点验 | 注册→登录→文本分析→编辑→保存→下载→刷新恢复→退出→管理员统计，全部通过 |
| 实际管理员1和2 | 各自登录200、后台200、注销后旧token401 |
| 安全用例 | 过期/无签名/错签名/错issuer/audience、无DB会话、停用、401/403、记录隔离、事务回滚、最后admin、委托提权拦截全部通过 |

78项=33接口+31AI单元+5访问控制+9安全测试；HTTP smoke中的AI是测试替身，真实模型12例另行执行。
测试及浏览器注册使用临时DB，没有在真实数据库留下测试用户或分析记录。
测试框架有Starlette关于httpx的弃用提示；当前测试通过，后续按框架升级计划调整即可。

## 请求、响应、数据库证据

完整脱敏证据位于 `access-control-evidence.json`，真实文本推理，无权限依赖替身。
包括register/login/me/analyze/records/403/匿名401/错误token401/logout/撤销401的每个请求与响应。
密码/token用 `<redacted>`；数据库只展示哈希算法、token哈希长度、角色关联及owner，未披露真实凭据。

主要实测结果：

```text
POST /api/auth/login {username:evidence_member,password:<redacted>} ->200 data.token:<redacted>
GET /api/auth/me Authorization:Bearer <redacted> ->200 member + analysis/records权限
POST /api/analyze Authorization:Bearer <redacted> ->200，真实结构化分析并保存owner
GET /api/records Authorization:Bearer <redacted> ->200，仅本人记录
GET /api/admin/overview（成员token）->403
GET /api/auth/me（不带token）->401
GET /api/auth/me（错误token）->401
POST /api/auth/logout ->200
GET /api/auth/me（已注销token）->401
```

真实本机数据库交付检查（2026-10-19 17:52）：

| 表/记录 | 实际值 |
| --- | --- |
| users | 2个，keyoushu_admin1、keyoushu_admin2，active=1，hash前缀$argon2id |
| roles / permissions | 3 / 11 |
| user_roles / role_permissions | 2 / 16 |
| records | 原有3条，保留；未自动归入普通成员 |
| auth_sessions | 2次验证登录，均已注销；token仅SHA256哈希 |

后续登录会改变会话与事件计数，上述为验收时快照。
真实数据库修改前使用SQLite backup API备份到本机 `.codex/local-backups/`；不提交仓库。
密码凭据位于 `.codex/local-credentials/keyoushu-admins.txt`，Windows权限仅当前用户。
实际模型验收完整转录保存在本机TEMP的 `keyoushu-auth-acceptance-20261019.json`。

## 文件与数据变更

- 后端新增：auth.py、auth_store.py、auth_routes.py、access_routes.py、audit.py、manage_users.py。
- 后端修改：main.py统一鉴权/错误/新增API；database.py迁移/归属；requirements.txt/.env.example。
- 前端新增：auth.js、LoginPanel.vue、AdminPanel.vue。
- 前端修改：App.vue、api.js、ResultPanel.vue（必要的认证与统计接入）。
- 测试新增：test_auth.py、test_access_control.py；适配test_api.py、smoke_http.py、check_acceptance.py。
- 文档：README、api.md、访问控制说明、SQL参考、脱敏HTTP/数据库证据及本记录。
- 新表7张：users、roles、permissions、user_roles、role_permissions、auth_sessions、access_events。
- 现表records新增owner_id与索引，原业务字段保持不变。具体接口和建表SQL另见相邻说明与schema文件。
- 用户原始 `更新功能/` 资料未改动，不加入本次提交；数据库、密码、环境配置和模型运行产物不提交。

## 尚未实现/信息不足

未实现找回密码、邮箱验证、日历、完整的用户/角色管理前端、分布式限流、历史访客补算。
PDF引用的18项细则文件缺失，不能对缺失原文逐条宣称验收通过。
统计是请求计数与已登录页面上报，不等同于实时在线人数或真人独立访客；copy_client为客户端上报。
本次不是main合并后的独立Agent-E正式验收；批准推送并完成团队PR审阅合并后仍须按原流程安排该项。

本地网站保持 `http://127.0.0.1:5173/`，后端 `http://127.0.0.1:8000/health`。
