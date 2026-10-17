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

输入：下面两种格式**二选一**，不能同时传。

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

### 错误

| 状态码 | 场景 | 返回 |
| --- | --- | --- |
| 400 | text 为空 | `{"detail": "聊天原文不能为空"}` |
| 400 | messages 为空数组 | `{"detail": "聊天消息不能为空"}` |
| 400 | 某条消息内容为空 | `{"detail": "第 1 条消息不能为空"}` |
| 422 | text 和 messages 都没传，或同时传了 | Pydantic 校验错误，`detail` 中说明原因 |
| 500 | 模型调用失败 | `{"detail": "<原因>"}` |

## 其余接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /health | 健康检查，返回 `{"status": "ok"}` |
| GET | /records | 历史列表：`id`、`title`、`created_at`、`updated_at` |
| GET | /records/{id} | 单条记录，含 `text` 和 `result` |
| PUT | /records/{id} | 保存编辑后的结果，请求体 `{"result": {...}}` |
| GET | /records/{id}/export | 导出该条记录为 JSON 文件 |

PUT `/records/{id}` 的 `result` 可以带 `is_sample`。如果前端没有传，
后端会保留这条记录原来的 `is_sample`，避免编辑保存后丢失“开发样例”标记。

## 当前状态

`ai_service.analyze_chat()` 现在返回**开发样例**（`is_sample: true`）。
D 接入真实模型后替换实现，以上格式不变。
