# AI 模块运行配置

项目后端使用 backend/ai_service.py 调用兼容 OpenAI Chat Completions 的云端模型，文本分析与截图转录均由该服务完成。请在 backend/.env 配置 FOLLOWUP_API_KEY、FOLLOWUP_BASE_URL、FOLLOWUP_MODEL 和 FOLLOWUP_REASONING_EFFORT；.env 已被 Git 忽略，不应提交。

截图仅用于聊天内容转录，转录文本会再进入同一分析流程。图片和聊天原文会发送到配置的模型服务，处理前应确认内容允许交由该服务处理。API Key 不写入源代码、日志、响应或仓库。

FOLLOWUP_QUALITY_REVIEW=true 时，服务会用同一原文再发起一次独立质量复核；设为 false 可减少每次分析的模型调用次数。模型结果仍会由后端校验 JSON 字段、角色来源和 evidence 原文引用，不符合约定的结果会被拒绝，不会退回本地规则模型。
