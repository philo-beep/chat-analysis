"""Strict model output and persisted analysis result contracts."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator


class RequirementModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    field: StrictStr = Field(min_length=1, max_length=100, pattern=r"\S")
    value: StrictStr = Field(min_length=1, max_length=1000, pattern=r"\S")
    evidence: StrictStr = Field(min_length=1, max_length=2000, pattern=r"\S")


class AIQuestion(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    question: StrictStr = Field(min_length=1, max_length=500, pattern=r"\S")
    initial_guess: StrictStr = Field(min_length=1, max_length=1000, pattern=r"\S")
    related_ddl_index: StrictInt | None


class DDLTask(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    title: StrictStr = Field(min_length=1, max_length=200, pattern=r"\S")
    ddl_date: StrictStr
    start_date: StrictStr | None
    source_quote: StrictStr = Field(min_length=1, max_length=2000, pattern=r"\S")
    date_basis: Literal["explicit", "inferred"]

    @field_validator("ddl_date", "start_date")
    @classmethod
    def iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError("日期必须是有效的 YYYY-MM-DD") from None
        if parsed.isoformat() != value:
            raise ValueError("日期必须是 YYYY-MM-DD")
        return value

    @field_validator("start_date")
    @classmethod
    def start_not_after_ddl(cls, value: str | None, info):
        ddl = info.data.get("ddl_date")
        if value and ddl and value > ddl:
            raise ValueError("开始日期不能晚于截止日期")
        return value


class SuggestedTask(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    title: StrictStr = Field(min_length=1, max_length=200, pattern=r"\S")
    reason: StrictStr = Field(min_length=1, max_length=1000, pattern=r"\S")
    priority: Literal["high", "medium", "low"]


class CustomerProfile(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    display_name: StrictStr = Field(max_length=200)
    role: StrictStr = Field(max_length=200)
    company: StrictStr = Field(max_length=300)
    industry: StrictStr = Field(max_length=200)
    concerns: list[StrictStr] = Field(max_length=3)
    decision_style: StrictStr = Field(max_length=500)
    communication_preferences: list[StrictStr] = Field(max_length=5)
    risk_points: list[StrictStr] = Field(max_length=10)
    next_follow_up: StrictStr = Field(max_length=1000)
    communication_strategy: StrictStr = Field(default="", max_length=1000)
    communication_points: list[StrictStr] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def coherent_guidance(self):
        if self.communication_points and (len(self.communication_points) < 3
                or any(not point.strip() or len(point) > 500 for point in self.communication_points)):
            raise ValueError("沟通要点须为 3–5 条非空、至多 500 字的说明")
        if bool(self.communication_strategy.strip()) != bool(self.communication_points):
            raise ValueError("沟通策略与要点应一同提供，信息不足时都留空")
        return self


class CustomerIdentity(BaseModel):
    """A source-checked counterparty identity, never a list of possible clients."""
    model_config = ConfigDict(strict=True, extra="forbid")
    display_name: StrictStr = Field(min_length=1, max_length=200)
    company: StrictStr = Field(min_length=1, max_length=300)
    name_quote: StrictStr = Field(max_length=1000)
    company_quote: StrictStr = Field(max_length=1000)


class AIOutput(BaseModel):
    """Exactly seven model-produced fields; profile is removed before API response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    requirements: list[RequirementModel] = Field(max_length=100)
    questions: list[AIQuestion] = Field(max_length=100)
    tasks: list[StrictStr] = Field(max_length=100)
    reply: StrictStr = Field(max_length=5000)
    ddl_tasks: list[DDLTask] = Field(max_length=100)
    suggested_tasks: list[SuggestedTask] = Field(max_length=100)
    customer_profile: CustomerProfile

    @model_validator(mode="after")
    def related_dates(self):
        linked = set()
        for question in self.questions:
            index = question.related_ddl_index
            if index is not None:
                if index < 0 or index >= len(self.ddl_tasks):
                    raise ValueError("待确认问题关联的任务序号无效")
                linked.add(index)
        if any(task.date_basis == "inferred" and index not in linked
               for index, task in enumerate(self.ddl_tasks)):
            raise ValueError("推算日期必须关联待确认问题")
        return self

    @field_validator("tasks")
    @classmethod
    def legacy_tasks_are_nonblank(cls, values):
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("tasks 每项须为 1–500 字的非空文字")
        return values

    @classmethod
    def response_schema(cls) -> dict:
        schema = cls.model_json_schema()
        # Old stored profiles may omit guidance; live strict output must include it.
        def require_all(node):
            if isinstance(node, dict):
                node.pop("default", None)
                if node.get("type") == "object" and "properties" in node:
                    node["required"] = list(node["properties"])
                for value in node.values():
                    require_all(value)
            elif isinstance(node, list):
                for value in node:
                    require_all(value)
        require_all(schema)
        return {
            "name": "keyoushu_sales_analysis",
            "strict": True,
            "schema": schema,
        }


class StoredQuestion(AIQuestion):
    status: Literal["pending", "confirmed", "dismissed"] = "pending"
    confirmed_answer: StrictStr | None = None


class StoredDDLTask(DDLTask):
    status: Literal["pending", "added"] = "pending"
    calendar_task_id: StrictInt | None = None


class StoredSuggestedTask(SuggestedTask):
    status: Literal["pending", "accepted", "ignored"] = "pending"
    task_item_id: StrictInt | None = None


class ActionState(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    status: Literal["pending", "accepted", "ignored", "added"]
    task_item_id: StrictInt | None = None


class RecordResult(BaseModel):
    """Read/write contract supporting both legacy and expanded analysis records."""

    # Existing clients send /analyze metadata (id) back with the editable result.
    model_config = ConfigDict(strict=True, extra="ignore")

    requirements: list[RequirementModel]
    questions: list[StrictStr | StoredQuestion]
    tasks: list[StrictStr]
    reply: StrictStr
    is_sample: StrictBool = False
    analysis_version: Literal[2] | None = None
    ddl_tasks: list[StoredDDLTask] | None = None
    suggested_tasks: list[StoredSuggestedTask] | None = None
    action_states: dict[str, ActionState] | None = None

    @model_validator(mode='after')
    def expanded_consistency(self):
        if self.analysis_version == 2 or self.ddl_tasks is not None or self.suggested_tasks is not None:
            if self.ddl_tasks is None or self.suggested_tasks is None:
                raise ValueError('扩展分析需同时包含日期任务和推进建议')
            for question in self.questions:
                if isinstance(question, StoredQuestion) and question.related_ddl_index is not None:
                    if not 0 <= question.related_ddl_index < len(self.ddl_tasks):
                        raise ValueError('关联日期任务无效')
        return self


class SaveRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    result: RecordResult

    @model_validator(mode="before")
    @classmethod
    def reject_profile_write(cls, value):
        if isinstance(value, dict) and isinstance(value.get('result'), dict) and 'customer_profile' in value['result']:
            raise ValueError('客户画像不能通过结果编辑提交')
        return value


class AnalysisAction(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    action: Literal["add_ddl_task", "accept_suggestion", "ignore_suggestion", "confirm_question"]
    kind: Literal["tasks", "suggested_tasks"] | None = None
    index: StrictInt = Field(ge=0, le=99)
    expected_result: dict
    answer: StrictStr | None = Field(default=None, max_length=1000)
