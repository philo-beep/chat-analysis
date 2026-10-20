# 日程计划 API

2026-10-20 扩展：下文自动同步 `tasks` 的说明仅适用于旧记录。新分析包含 `ddl_tasks / suggested_tasks`，普通及推进建议需显式采纳，日期任务需点击加入日历，复用同一任务表。模型可提供 `start_date`，导入时后端可信写入；浏览器仍不能直接提交开始日。具体结构、日期推算和验收限制见 [扩展分析交付](expanded-ai-delivery.md)。日历自身的颜色、完成、甘特及帮助规则未改变。

沿用 FastAPI、SQLite 与 Bearer token。所有响应为 `{code,message,data}`，成功 `code=0`；失败使用 HTTP 状态码和同值 `code`，`data=null`。读取需 `records:read`，修改需 `records:write`；来源导入两者都需具备。日程始终按当前用户隔离，管理员也不能直接读写他人日程。

## 数据与日期

`task_items` 是唯一任务表，有无 DDL 共用，不改分析结果的 `tasks: string[]` 契约。新建分析记录及保存分析结果编辑时，后端会把新的建议任务事务性同步到当前账号的个人日历；已同步的键不会重复创建。建议中明确写有 `DDL: YYYY-MM-DD`、`截止日期：YYYY-MM-DD` 或 `截止时间：YYYY-MM-DD` 时写入 DDL 并按自动等级计算；其他建议进入无 DDL 待办池。相对日期或没有年份的日期不会猜算。启动迁移会一次性补同步旧聊天建议。来源建议后来被编辑或移除时，只新增尚未同步的建议，不自动改写或删除已有日历事项；已有事项属于个人日程，可继续保留其用户设置的 DDL、等级和完成状态，并应在日历中单独管理。

删除历史聊天使用 `DELETE /api/records/{id}`，要求 `records:write` 且只能删除当前账号自己的记录；响应返回 `deleted_calendar_tasks` 数量。仅删除该账号日历中关联的来源待办、排期及已完成事项；手工创建事项和其他用户日历中的导入副本不受影响（来源聊天删除后，其他账号的副本解除来源关联）。删除聊天及该账号任务在同一事务完成。历史列表响应提供逐条 `can_delete` 标记，前端只对当前用户拥有且可删除的记录显示删除按钮。前端执行前展示影响说明并要求用户确认，取消或请求失败都保留原聊天及该账号关联日历事项。

任务字段：`id,title,notes,due_date,start_date,manual_level,created_at,updated_at,completed_at,source_record_id,source_task_key`；计算字段：`effective_start_date,is_manual,completed,urgency_level,is_overdue,date_anomaly`。

- 日期为 `YYYY-MM-DD`。时间戳为带 `+08:00` 的 ISO 格式；业务日期采用 `Asia/Shanghai`。
- `effective_start_date` 优先取后端 `start_date`，缺失时取创建时间的业务日期。当前 AI 返回字符串建议，不提供可信开始日期，手动创建和导入均为 `start_date:null`；客户端禁止提交开始日、创建时间、归属用户。
- `manual_level` 可空，空为自动。距离 DDL 的天数 `d` 按今天计算：`<=2` 为 5，3–4 为 4，5–6 为 3，7–8 为 2，>=9 为 1。无 DDL 自动等级为空。
- `is_overdue` 为 DDL 早于今天且未完成；逾期显示优先于等级，手动等级原值保留。
- `date_anomaly` 表示 DDL 早于有效开始日。接口保留原日期，供界面标明异常，不伪造开始日。
- 标记完成保存实际 `completed_at`；再次完成不改变结束时间。重新打开将其清空。默认列表排除已完成。

## 接口

统一前缀 `/api/calendar`。

| 方法与路径 | 请求 | data |
|---|---|---|
| POST `/items` | `{title,notes?,due_date?,manual_level?}` | 任务对象 |
| GET `/items/{id}` | 正整数 ID | 任务对象 |
| PATCH `/items/{id}` | 至少一个：`title,notes,due_date,manual_level` | 更新任务 |
| PATCH `/items/{id}/completion` | `{completed:true/false}` | 更新任务 |
| DELETE `/items/{id}` | ID | `{id,deleted:true}` |
| GET `/items` | 见下文 | `{items,total,today,timezone}` |
| POST `/items/from-record` | `{record_id,task_index,expected_text}`，序号从 0 开始 | 导入任务 |

标题去除首尾空白后非空，最多 200 字；备注最多 5000 字。日期必须有效；等级必须为整数 1–5。未知字段、空标题、`title:null`、`notes:null` 均拒绝；`due_date:null` 移回待办池，`manual_level:null` 恢复自动。

列表参数：

- `from`、`to`：可选、含边界的日期范围，开始不能晚于结束；返回与有效日程区间重叠的有 DDL 任务。未完成逾期任务查询范围延伸至今天，支持甘特超时段；反向日期异常按 DDL 标记可查。
- `scheduled=true/false`：有／无 DDL；`false` 不能与日期范围同时使用。
- `status=open/completed/all`：默认 `open`。
- `limit`：1–500，默认 500；`offset`：>=0，默认 0。`total` 是分页前筛选数量。

来源导入在事务中核对持久化建议文本及序号；未保存或已变化返回 409，刷新保存后重试。相同用户、来源、序号、文本重复导入返回同一任务；来源记录改动不会覆盖已导入任务。长建议前 200 字为标题，完整文本保存在备注（上限 5000 字）。持有 `records:all` 可读取来源的管理员也只能导入到自己的待办池。

错误：401 未登录或 token 无效，403 无权限，404 不存在或其他用户事项，409 来源快照变化／损坏，422 输入无效。所有写入使用现有数据库事务；来源核对与导入同一事务完成。

## 自验

`backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p test_calendar.py -v`

使用临时数据库，覆盖待办→排期→手动等级→自动恢复→逾期→完成→重开→删除、等级边界、开始日期优先、账号隔离（含管理员）、401/403、输入校验、区间及分页、来源幂等及变更冲突、旧表升级。不会访问真实 `backend/app.db`。
