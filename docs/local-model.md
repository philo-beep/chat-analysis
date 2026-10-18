# 本地分析模型

文本使用桌面 `ai_followup_trainer` 已训练的字符 n-gram 朴素贝叶斯模型。权重和 `scripts/common.py` 原样复制到 `backend/followup_engine/models/char_ngram_nb.json`、`upstream_common.py`，不改动来源目录。权重 SHA-256：`8ec5c3a4f8ef925f35028102bb2ca2f7f5c33ea0708d9f9861c1443b8bd5ae87`。

每次分析实际调用原 `classify`（内部使用 `tokenize`），并用原 `rule_intent` 为无明确事实的咨询选择建议待办；已提取文化衫事实时使用经过检查的报价/交期建议模板。`adapter.py` 针对文化衫订单提取需求，保留客户原文证据，过滤商家发言。明确修改覆盖旧值；未确认的预算冲突同时保留并追问；相对日期不换算为绝对日期，没有年份就追问。单价预算不会乘数量捏造总预算。真实结果一律 `is_sample=false`，模型缺失/损坏直接失败。

截图使用本机 Ollama `qwen2.5vl:7b` 逐字转录，随后进入同一文本管道。转录保留客户/商家角色；角色不清晰的消息不作为已确认事实。图片上的提示词不作为操作指令。截图转录是模型识别结果，仍需人工对照原图检查错字和角色，页面同时保留原图、转录及证据。

本次做了现成 NB 模型接入、规则适配和 Qwen 转录提示词工程。**没有执行 LoRA，也没有训练 Qwen 权重**，不能将其称作微调模型。

## 启动

```powershell
ollama serve
ollama pull qwen2.5vl:7b
Copy-Item backend/.env.example backend/.env
```

Ollama 已启动时不重复执行 `serve`。后端启动方式见 README。`FOLLOWUP_MODEL_PATH` 可指定另一份兼容 NB 权重；默认使用项目副本。`OLLAMA_BASE_URL` 只接受本机 HTTP 地址；`OLLAMA_VISION_MODEL` 默认为 `qwen2.5vl:7b`；`OLLAMA_TIMEOUT` 默认为 600 秒。环境变量在调用时读取，兼容 main 在模块导入之后加载 `.env`。

视觉请求使用进程内线程锁串行推理，锁等待和单次 HTTP 调用分别有超时；首次加载或 CPU 推理可能较慢，请等待页面加载结束。请求禁用代理与重定向，拒绝 cloud 模型名，转录被长度限制截断时直接报错。Ollama 未运行、模型未下载、识别为空或超时会显示可重试错误，不会返回开发样例。多进程部署需另行统一视觉队列；当前本机按单 worker 运行。

## 检查

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p test_ai_service.py -v
```

31 项测试涵盖文档五场景、甲乙角色、客户姓名、未见数量/预算、数字区间、否定/问句、旧订单过滤、单价与总预算分离、运费/定金/报价排除、客户供稿、精确证据、NB 实际调用、运行时环境变量以及截图失败路径。真实截图验收另见 `docs/d-progress.md`。
