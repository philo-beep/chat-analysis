# 接口约定（C 维护）

前后端按本文件同时开工。**字段名称、数据类型、空值规则一旦确定，改动必须先在群里说明。**

## 责任边界（谁管哪一段）

每个人负责一个板块，板块之间靠本文件对接。分工是：

| 环节 | 谁负责 | 边界 |
| --- | --- | --- |
| 本文件（字段名、类型、空值规则） | C | **C 定规则**，别人不单方面改 |
| 前端把用户输入变成请求、把结果画成页面 | A、B | 按本文件的请求/响应格式收发 |
| 接口、入参整理和数据库 | C | `main.py`、`database.py`；把 `text` / `messages` 统一成 AI 文本 |
| `analyze_chat(text)` 的真实模型调用 | D | **输入 C 整理好的一个字符串，输出必须是下面 4 个字段** |

最容易出问题的就是 D 这一段：D 只负责"给一段聊天，还回一个符合格式的对象"，
具体页面怎么显示、存在哪里、原先是一整段还是逐条消息，都不是 D 的事。
只要格式对得上，前端和 D 都不用跟着改。

## POST /analyze

输入：JSON `text` / `messages` 二选一，或 multipart 的 `text` + `image`。

输出：需求、待确认问题、建议待办、回复草稿

### 请求 A：一整段聊天原文

```json
{
  "text": "我们想定制 100 件文化衫"
}
```

| 字段 | 类型 | 必填 | 空值规则 |
| --- | --- | --- | --- |
| text | string | 是 | 前后空白会被忽略，全空白返回 400 |

客户名称放在 `text` 内，不新增单独字段。分析时忽略首尾空白，数据库保留用户提交的完整原始字符串，便于核对。

### 请求 B：逐条消息

```json
{
  "messages": [
    {
      "speaker": "客户",
      "content": "我们想定制 100 件文化衫",
      "time": "10:01"
    },
    {
      "role": "seller",
      "content": "好的，请问什么时候要？"
    },
    "这一条没有写说话人也可以"
  ]
}
```

| 字段 | 类型 | 必填 | 空值规则 |
| --- | --- | --- | --- |
| messages | array | 是 | 至少一条；不能是空数组 |
| messages[] | object \| string | 是 | 字符串会当成一条“未标注”消息 |
| messages[].speaker | string | 否 | 显示名称，例如“客户”“商家” |
| messages[].role | string | 否 | 角色，例如 `customer`、`seller` |
| messages[].content | string | 是 | 前后空白会被去掉，不能为空白 |
| messages[].time | string | 否 | 消息时间，会保留在整理后的文本里 |

为兼容不同前端，消息对象里的 `content` 也可以写成 `text`，`time` 也可以写成
`timestamp`；同时存在时优先使用 `content` / `time`。

角色会统一成 `customer`、`seller` 或 `unknown`。常见的中英文写法都能识别，
例如“客户 / 顾客 / 甲方 / customer / user”会统一成 `customer`，
“商家 / 卖家 / 乙方 / 客服 / seller / assistant”会统一成 `seller`。

### C 如何整理并交给 D

`backend/main.py` 的 `normalize_analyze_request()` 会把两种请求都整理成一个
Python 字典，再只把其中的 `text` 交给 `analyze_chat(text)`：

```python
{
    "source": "messages",
    "text": "[10:01 客户] 我们想定制 100 件文化衫\n[商家] 好的，请问什么时候要？\n[未标注] 这一条没有写说话人也可以",
    "messages": [
        {"role": "customer", "speaker": "客户", "content": "我们想定制 100 件文化衫", "time": "10:01"},
        {"role": "seller", "speaker": "商家", "content": "好的，请问什么时候要？", "time": None},
        {"role": "unknown", "speaker": "未标注", "content": "这一条没有写说话人也可以", "time": None},
    ],
    "message_count": 3,
}
```

这份整理结果是后端内部数据，不会额外出现在响应里。D 的调用方式保持：

```python
result = analyze_chat(chat["text"])
```

有显示姓名且另有明确角色时，模型输入形如 `[客户(张先生)] …`，避免显示姓名遮盖角色。
原始 JSON 请求另外保存到详情的 `source_input`，包括原始消息内容、姓名和时间。
消息内容同时提供 `content` 与 `text` 时，严格采用 `content`，空白 `content` 不会回退到另一个字段。

### 请求 C：聊天截图

```bash
curl -F "text=客户名称：张先生" -F "image=@chat.png" http://127.0.0.1:8000/analyze
```

- `Content-Type: multipart/form-data`；`image` 必须为图片文件，`text` 为可选字符串，可以为空。
- 只支持 PNG、JPEG、WebP，最大 10 MiB；校验真实图片格式、完整解码和声明 MIME 一致性，最多 2500 万像素。请求整体上限为 10 MiB + 64 KiB。
- 不接受客户端直接提交的图片 data URL；必须通过 `image` 文件上传。`source_image` 只由服务端生成，因此具有同一大小限制。
- C 将经过校验的原始图片字节、MIME 和去除首尾空白的文字传给 D：`analyze_chat_with_source(text, image_bytes, image_mime)`。
- D 返回内部 `ai_contract.AnalysisOutcome(result, source_text)`，`source_text` 为含客户/商家角色的截图逐字转录，不能代替结构化结果。
- 保存完整原始文字、原图和截图转录。`record.text` 为原始文字加 `[聊天截图转录]` 段；真实模型的每条 evidence 必须能在该文本找到。截图转录仍需人工对照原图核实。
- 图片处理在线程池内执行，不阻塞健康检查。模型超时由 D 的本地调用设置，建议不少于 180 秒；失败不生成记录，没有样例回退。

### 响应

```json
{
  "requirements": [
    {
      "field": "数量",
      "value": "100 件",
      "evidence": "我们想定制 100 件文化衫"
    }
  ],
  "questions": ["请确认尺码分布"],
  "tasks": ["准备初步设计方案"],
  "reply": "收到，请再提供一下尺码分布，方便准备方案。",
  "id": 12,
  "is_sample": false
}
```

| 字段 | 类型 | 空值规则 |
| --- | --- | --- |
| id | number | 本次分析保存后的记录编号，从 1 开始 |
| requirements | array | 无内容时为 `[]`，**不返回 null** |
| requirements[].field | string | 必填，不可为空字符串 |
| requirements[].value | string | 必填；原文未明确时填 `"待确认"` |
| requirements[].evidence | string | 必须是原文片段，不可编造 |
| questions | string[] | 无内容时为 `[]` |
| tasks | string[] | 无内容时为 `[]` |
| reply | string | 无内容时为 `""`，不返回 null |
| is_sample | boolean | `true` 表示这条是开发样例、不是真实模型结果；前端据此在页面上标注 |

> `is_sample` 存在的意义：D 还没接上真实模型时，页面上必须能看出"这是假数据"，
> 免得验收时把开发样例当成真实效果。

四个业务字段必须全部提供；空数组和空回复字符串合法，缺失字段、`null` 或错误类型不合法。
需求项的 `field`、`value`、`evidence` 都必须为非空、非全空白的字符串；需求项不接受未知字段。
`questions`、`tasks` 必须是字符串数组，不会将数字或对象自动转成字符串。
真实分析（`is_sample: false`）的每条 `evidence` 还会按原文片段校验；不在输入原文中的引用会使本次分析失败，且不保存记录。
开发样例允许使用固定引用，但始终保留样例标记。

D 的函数可以只返回四个业务字段，未提供的 `is_sample` 默认补为 `false`；开发样例必须显式返回 `true`。
这只能验证结构与引用来源，不能保证数量、预算、改口等语义正确，语义质量仍由 D/E 使用测试样例验收。

### 错误

| 状态码 | 场景 | 返回 |
| --- | --- | --- |
| 400 | text 为空 | `{"detail": "聊天原文不能为空"}` |
| 404 | 详情、保存、导出的记录不存在 | `{"detail": "记录不存在"}` |
| 422 | 请求字段缺失、字段类型或嵌套结构错误 | FastAPI 的 `detail` 错误数组，包含错误字段路径 |
| 500 | 真实模型尚未接入 | `{"detail": "真实模型调用尚未实现，请联系 D 完成接入"}` |
| 500 | 模型超时 | `{"detail": "模型调用超时，请稍后重试"}` |
| 500 | 其他模型异常 | `{"detail": "模型调用失败，请稍后重试；持续失败请联系 D"}` |
| 500 | 模型结果结构不合法 | `{"detail": "模型返回结果格式不符合接口约定，请联系 D 检查"}` |
| 500 | 真实模型引用不在原文中 | `{"detail": "模型返回的原文引用无效，请联系 D 检查"}` |
| 500 | 数据库读写失败 | `{"detail": "数据库操作失败，请联系 C 检查服务端日志"}` |
| 500 | 历史记录的结果 JSON 损坏或不是对象 | `{"detail": "历史记录内容损坏，请联系 C 检查服务端日志"}` |
| 400 | messages 为空数组或单条消息为空 | `{"detail": "聊天消息不能为空"}` 或 `{"detail": "第 1 条消息不能为空"}` |
| 400 | JSON 无法解析、图片空白或损坏 | 具体中文提示 |
| 413 | 图片/请求超限或图片像素过多 | 具体中文提示 |
| 415 | 请求类型不支持、图片格式不支持或 MIME 不一致 | 具体中文提示 |
| 422 | text/messages 都未传、同时提供或表单字段不符合约定 | 校验错误；JSON 返回错误数组 |

分析阶段失败不会创建记录；保存返回 500 时不得显示保存成功。服务端日志保留异常堆栈和失败阶段，客户端不返回上游内部异常原文。
前端应读取 `detail` 展示具体原因，422 则可根据字段路径提示；网络连接失败由前端提示检查后端是否启动。

## 其余接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /health | 健康检查，返回 `{"status": "ok"}` |
| GET | /records | 历史列表：`id`、`title`、`created_at`、`updated_at` |
| GET | /records/{id} | 单条记录，含 `text` 和 `result` |
| PUT | /records/{id} | 保存编辑后的结果，请求体 `{"result": {...}}` |
| GET | /records/{id}/export | 导出该条记录为 JSON 文件 |

### 详情与保存的对接约定

`GET /records` 按记录编号倒序返回最近 100 条摘要，不包含结果。点击历史后需要请求详情，不能直接使用摘要中的 `result`。

详情结构示意（时间字符串为本地 ISO 时间）：

```json
{
  "id": 12,
  "title": "客户甲：我们想定制 100 件文化衫",
  "text": "客户甲：我们想定制 100 件文化衫",
  "result": {
    "requirements": [],
    "questions": ["请确认具体数量和预算"],
    "tasks": [],
    "reply": "收到，请再确认具体要求。",
    "is_sample": true
  },
  "created_at": "2026-10-17T12:00:00",
  "updated_at": "2026-10-17T12:00:00"
}
```

保存请求：

```http
PUT /records/12
Content-Type: application/json
```

```json
{
  "result": {
    "requirements": [
      {"field": "数量", "value": "150 件（人工修改）", "evidence": "数量改为150件"}
    ],
    "questions": ["请确认尺码分布"],
    "tasks": ["核算报价"],
    "reply": "收到，数量按150件记录。"
  }
}
```

- 保存成功返回 `{"ok": true}`。这是完整替换四个业务字段的 PUT，不是部分更新；只传 `reply` 会返回 422。
- `is_sample` 是分析来源标记，由服务端保留原值。保存时可省略，即使回传相反的值也不会改变来源；缺少来源标记的旧记录仍保持缺失，不被擅自标为真实结果。
- 可兼容将 `/analyze` 的整个响应作为 `result` 回传；顶层 `id` 等未声明的展示元数据不会写入结果。需求项内部仍严格校验字段。
- 人工编辑允许修改需求和引用，保存接口验证结构；“引用必须出自原文”的自动检查仅针对真实模型新生成的结果。
- A/B 需要分别保存当前 `recordId` 和结果草稿：新分析时使用响应的 `id`，历史打开时使用详情顶层的 `id`。仅设置 `result = full.result` 会丢失后续保存所需的编号。
- A/B 在保存按钮中调用 `saveRecord(recordId, draft)`，等待成功后再提示；刷新后通过详情重新读取，不能只检查页面草稿。
- 后端导出包含编号、原文、结果和时间，响应带 `Content-Disposition: attachment; filename="record-12.json"`，内容为 UTF-8 JSON。
- 图片记录的详情和导出另外包含 `source_input`（原始输入对象）、`source_image`（原图 data URL）和 `source_transcript`（截图转录）。纯文本无图片时分别为原始对象、`null`、`""`。
- 启动时自动给旧数据库增加这三列，保留旧结果和原文，旧记录的 `source_input` / `source_image` 为 `null`、`source_transcript` 为 `""`。列表摘要保持原有四字段，不携带图片。

## 当前状态

2026-10-18：C 接口保留远端逐条消息功能，增加截图透传、原图/转录持久化和兼容迁移。
D 的本地现成文本模型、截图 Qwen 模型和项目适配由 D 维护；C 的测试替身只验证接口边界，不代表真实 AI 业务样例通过。
完整验收结果由 E 基于全部合并后的真实运行报告确认。
