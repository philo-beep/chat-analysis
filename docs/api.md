# 接口约定（C 维护）

前后端按本文件同时开工。**字段名称、数据类型、空值规则一旦确定，改动必须先在群里说明。**

## POST /analyze

输入：聊天原文

输出：需求、待确认问题、建议待办、回复草稿

### 请求

```json
{
  "text": "我们想定制 100 件文化衫"
}
```

| 字段 | 类型 | 必填 | 空值规则 |
| --- | --- | --- | --- |
| text | string | 是 | 前后空白会被忽略，全空白返回 400 |

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
  "reply": "收到，请再提供一下尺码分布，方便准备方案。"
}
```

| 字段 | 类型 | 空值规则 |
| --- | --- | --- |
| requirements | array | 无内容时为 `[]`，**不返回 null** |
| requirements[].field | string | 必填，不可为空字符串 |
| requirements[].value | string | 必填；原文未明确时填 `"待确认"` |
| requirements[].evidence | string | 必须是原文片段，不可编造 |
| questions | string[] | 无内容时为 `[]` |
| tasks | string[] | 无内容时为 `[]` |
| reply | string | 无内容时为 `""`，不返回 null |

响应中额外带上 `id`，是本次分析保存后的记录编号。

### 错误

| 状态码 | 场景 | 返回 |
| --- | --- | --- |
| 400 | text 为空 | `{"detail": "聊天原文不能为空"}` |
| 500 | 模型调用失败 | `{"detail": "<原因>"}` |

## 其余接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /health | 健康检查，返回 `{"status": "ok"}` |
| GET | /records | 历史列表：`id`、`title`、`created_at`、`updated_at` |
| GET | /records/{id} | 单条记录，含 `text` 和 `result` |
| PUT | /records/{id} | 保存编辑后的结果，请求体 `{"result": {...}}` |
| GET | /records/{id}/export | 导出该条记录为 JSON 文件 |

## 当前状态

`ai_service.analyze_chat()` 现在返回**开发样例**（`is_sample: true`）。
D 接入真实模型后替换实现，以上格式不变。
