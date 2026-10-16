"""AI 调用与结果处理，D 负责。

现在返回**明确标注的开发样例**，让前端和接口先跑通；
D 实现真实模型调用后，把 _dev_sample() 换掉即可，返回格式保持不变。
"""

import os

DEVELOPMENT_SAMPLE = True  # D 接入真实模型后改为 False


def _dev_sample(text: str) -> dict:
    """开发用示例结果，字段与 docs/api.md 完全一致。"""
    return {
        "requirements": [
            {
                "field": "数量",
                "value": "100 件",
                "evidence": "我们想定制 100 件文化衫",
            }
        ],
        "questions": ["请确认尺码分布"],
        "tasks": ["准备初步设计方案"],
        "reply": "收到，请再提供一下尺码分布，方便准备方案。",
        "is_sample": True,
    }


def analyze_chat(text: str) -> dict:
    """独立实现：输入聊天原文，返回约定格式的分析结果。"""
    if DEVELOPMENT_SAMPLE or not os.getenv("OPENAI_API_KEY"):
        return _dev_sample(text)

    # TODO(D): 真实调用模型，并保证返回值仍是 requirements / questions /
    # tasks / reply 四个字段，空值规则见 docs/api.md。
    raise NotImplementedError("真实模型调用待 D 实现")
