"""截图分析的内部返回类型，不扩展公开 /analyze 响应。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisOutcome:
    result: dict
    # 截图逐字转录，保留说话角色；C 负责与用户提交的原始 text 合并保存。
    source_text: str
