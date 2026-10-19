# 注册、登录与后台访问控制

本次在现有 FastAPI、Vue 3、SQLite 上实现，沿用本地 NB 文本模型与本机 Qwen 截图服务。
参考 `更新功能/访问控制.md`、`更新功能/architecture.pdf`，用户追加要求覆盖原文排除的“注册”边界。
PDF 引用的 `docs/login-access-tasks.md`（18条验收）及 `docs/architecture.md` 未提供，不能声称逐条完成这份缺失清单。

## 账号与运行

1. `pip install -r backend/requirements.txt` 安装 Argon2 和 JWT 所需依赖。
2. 后端启动时事务性初始化/迁移 SQLite；部署现有数据前请先用 SQLite backup API 备份。
3. 在 backend 运行 `.venv/Scripts/python.exe manage_users.py --bootstrap-admins` 创建两个管理员。
4. 管理员默认名 `keyoushu_admin1`、`keyoushu_admin2`，随机密码彼此不同，只存当前用户
   `~/.codex/local-credentials/keyoushu-admins.txt`；Windows 去除继承 ACL，只授当前用户访问。该文件不进仓库。
5. 普通成员在前端“去注册”创建。用户名3–64位字母、数字、汉字、下划线、点或短横线，密码10–128字符。
6. 前端 `npm run dev -- --host 127.0.0.1 --port 5173`；后端 `uvicorn main:app --host 127.0.0.1 --port 8000`。

注册只创建 member，不接受 role/permission/owner_id。没有默认管理员密码或匿名创建管理员入口。
已存在账号或凭据文件会使 bootstrap 整批回滚；CLI `create --username NAME --role admin` 使用 getpass 输入密码。
本机密码与数据库并不会随代码克隆到其他电脑，队友需独立初始化账号。

## 鉴权与数据隔离

密码使用 Argon2id，JWT 固定 HS256、有效期3600秒，签名密钥来自 `KEYOUSHU_JWT_SECRET`（至少32字符），
未设置时安全生成到 `~/.codex/local-credentials/keyoushu-jwt.key`。不要把实际密钥写入 `.env.example`。
token存在 localStorage 的 `keyoushu.auth.token`，请求通过 Authorization header 传递，不放URL。
每次后端统一依赖校验签名、issuer、audience、必需claim、过期、数据库token哈希会话、用户active与实时权限。
注销撤销会话，停用撤销用户全部会话；重新启用不会恢复旧token。历史记录缓存按用户ID隔离。

管理写操作除了对应权限，还要求内置 admin 角色，防止委托管理者提升自己权限；最后有效管理员不能被停用/降级。
内置admin必须保留全部系统权限。角色关联批量变更使用事务；无效ID使整批失败，不部分写入。

新记录 owner_id 来自鉴权用户，普通成员读/改/导出都在SQL条件中校验归属；他人记录返回404。
拥有 `records:all` 且具备相应操作权限的账号可跨用户访问。原记录owner为NULL保留，普通成员不可见。
数据库内部无scope调用供旧测试/受信本机脚本使用，新HTTP入口必须显式传入受信用户scope，禁止直接暴露内部全量读取函数。

登录/注册有进程内、5分钟窗口限流：每来源IP/动作30次，每来源IP+用户名/动作10次；成功登录清除用户名失败队列。
统计不应被当成反爬或分布式风控；多进程/公网部署前需共享限流存储、HTTPS和独立部署配置。

## 接口

新接口成功 `{ "code":0,"message":"...","data":... }`；失败HTTP状态401/403/404/409/422/429/500，
响应 `{ "code":状态码,"message":"...","data":null }`。校验错误不回显密码等输入。
旧业务端点维持原JSON与detail错误形状，但同样鉴权，避免绕过。

| 方法、路径 | 输入 | data输出 | 权限 |
| --- | --- | --- | --- |
| POST /api/auth/register | username,password | {user} | 公开，固定member |
| POST /api/auth/login | username,password | token,token_type,expires_in,user | 公开，限流 |
| GET /api/auth/me | Bearer | 用户、roles、permissions | 登录 |
| POST /api/auth/logout | Bearer | null | 登录 |
| GET /api/access-control/users | limit 1–100,offset≥0 | items,total,limit,offset | users:read |
| POST /api/access-control/users | username,password,role_ids | 用户 | admin + users:write |
| PUT /api/access-control/users/{id}/roles | role_ids | 用户 | admin + users:write |
| PATCH /api/access-control/users/{id} | is_active布尔 | 用户 | admin + users:write |
| GET /api/access-control/roles | 无 | 角色列表含permission_ids | roles:read |
| POST /api/access-control/roles | code,name | 角色 | admin + roles:write |
| PUT /api/access-control/roles/{id}/permissions | permission_ids | id,permission_ids | admin + roles:write |
| GET /api/access-control/permissions | 无 | 权限列表 | permissions:read |
| POST /api/analyze | 原text/messages或multipart | 原分析结果 | analysis:run |
| GET /api/records | 无 | 最近100条可见记录 | records:read + 归属 |
| GET /api/records/{id} | 无 | 记录 | records:read + 归属 |
| PUT /api/records/{id} | result | {ok:true} | records:write + 归属 |
| GET /api/records/{id}/export | 无 | 记录 | records:export + 归属 |
| POST /api/usage/visit | {} | null | 登录 |
| POST /api/usage/copy | record_id | null | records:read + 归属 |
| GET /api/admin/overview | days 1–90，默认7 | users,records,visits,features,daily,note | admin:stats |
| GET /api/admin/events | days,limit 1–200,offset | total,items | admin:stats |

member 默认 analysis:run、records:read/write/export；viewer 仅 records:read；admin有全部11项权限。
`/health` 公开用于存活检查，`/docs`与`/openapi.json`仅公开接口结构，不含业务数据。

## 数据库结构

精确建表SQL见 `access-control-schema.sql`。用户、角色、权限、两张关联表为RBAC五表，
另有 `auth_sessions`（token SHA256哈希、过期与撤销时间）与 `access_events`（元数据统计）。
每连接启用 foreign_keys、busy_timeout；关联表复合主键及反向索引，用户名COLLATE NOCASE UNIQUE。
启动迁移使用 BEGIN IMMEDIATE，原records新增nullable owner_id外键和(owner_id,id DESC)索引。
角色初次创建时授予初始权限；重复启动不会恢复管理员已撤销的member权限。

## 统计口径与边界

从本版本部署后开始采集；已登录页面打开/切换作为visit，不推断匿名访客，账号去重并非独立真人。
成功/失败按HTTP状态200–299区分。统计涵盖登录、注册、退出、分析、历史、详情、保存、导出、管理操作。
`copy_client`为剪贴板成功后的客户端事件，只能证明收到上报，不是服务端可证实的剪贴板操作。
计数以请求为单位，重试会多计；日期UTC，滚动days窗口。概览查询采用同一读事务快照，避免并发访问造成互相矛盾的计数。
仅保存时间、账号ID、功能、固定路由模板、方法、状态码、耗时。不保存密码、token、请求体、聊天正文、查询参数或未知网址。
失败登录不记录用户输入的用户名（显示匿名）。后台统计自身读取也记事件；刚发出的统计请求会在下次刷新出现。
不做注册邮箱验证、找回密码、日历、用户管理前端、实时在线人数或持久化分布式限流。事件留存清理需后续部署运维策略。

## 验证

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
backend/.venv/Scripts/python.exe backend/tests/smoke_http.py
backend/.venv/Scripts/python.exe backend/tests/check_acceptance.py --images --output "$env:TEMP/keyoushu-acceptance.json"
cd frontend
npm run build
```

测试使用临时数据库，真实登录，不绕过权限依赖。AI单元/HTTP smoke使用模型替身；check_acceptance是真实模型。
交付证据与实际运行结果见 `access-control-delivery.md`。
