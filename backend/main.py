"""接口入口，C 负责。

接口约定见 docs/api.md，字段名称 / 数据类型 / 空值规则都要固定。
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

import database
from ai_service import analyze_chat

# 读 backend/.env（复制 .env.example 得到）。密钥只在本机，不进仓库。
load_dotenv(Path(__file__).parent / ".env")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="聊天分析 API", version="0.1.0", lifespan=lifespan)

# 开发阶段允许前端本地地址跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessageIn(BaseModel):
    """一条聊天消息。

    speaker 和 role 可以提供一个；都没有时按“未标注”处理。content 和 text
    是内容字段的两种写法，content 优先。兼容常见的 {"role", "content"} 前端消息格式。
    """

    speaker: str | None = Field(None, description="显示名称，例如：客户、商家")
    role: str | None = Field(None, description="角色，例如：customer、seller")
    content: str | None = Field(None, description="消息内容")
    text: str | None = Field(None, description="消息内容的兼容写法")
    time: str | None = Field(None, description="消息时间，可选")
    timestamp: str | None = Field(None, description="消息时间的兼容写法")


class AnalyzeRequest(BaseModel):
    """分析请求：整段 text 和逐条 messages 二选一。"""

    text: str | None = Field(None, description="一整段聊天原文")
    messages: list[ChatMessageIn | str] | None = Field(
        None, description="逐条聊天消息，支持对象或字符串"
    )

    @model_validator(mode="after")
    def require_one_input(self) -> "AnalyzeRequest":
        if self.text is None and self.messages is None:
            raise ValueError("请提供 text 或 messages")
        if self.text is not None and self.messages is not None:
            raise ValueError("text 和 messages 只能提供一个")
        return self


class NormalizedMessage(TypedDict):
    role: Literal["customer", "seller", "unknown"]
    speaker: str
    content: str
    time: str | None


class NormalizedChat(TypedDict):
    source: Literal["text", "messages"]
    text: str
    messages: list[NormalizedMessage]
    message_count: int


class ResultModel(BaseModel):
    requirements: list = []
    questions: list = []
    tasks: list = []
    reply: str = ""
    is_sample: bool | None = None


class SaveRequest(BaseModel):
    result: ResultModel


_CUSTOMER_ROLES = {
    "customer",
    "client",
    "buyer",
    "user",
    "顾客",
    "客户",
    "甲方",
    "买家",
    "用户",
}
_SELLER_ROLES = {
    "seller",
    "merchant",
    "assistant",
    "客服",
    "商家",
    "卖家",
    "乙方",
    "销售",
}
_ROLE_LABELS = {"customer": "客户", "seller": "商家"}


def _normalize_role(role: str | None, speaker: str | None) -> str:
    value = (role or speaker or "").strip().lower()
    if value in _CUSTOMER_ROLES:
        return "customer"
    if value in _SELLER_ROLES:
        return "seller"
    return "unknown"


def _normalize_message(item: ChatMessageIn | str, index: int) -> NormalizedMessage:
    if isinstance(item, str):
        content = item.strip()
        if not content:
            raise HTTPException(status_code=400, detail=f"第 {index} 条消息不能为空")
        return {
            "role": "unknown",
            "speaker": "未标注",
            "content": content,
            "time": None,
        }

    content = (item.content or item.text or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail=f"第 {index} 条消息不能为空")

    speaker = (item.speaker or "").strip()
    role = _normalize_role(item.role, speaker)
    message_time = (item.time or item.timestamp or "").strip() or None
    return {
        "role": role,
        "speaker": speaker or _ROLE_LABELS.get(role, "未标注"),
        "content": content,
        "time": message_time,
    }


def _render_message(message: NormalizedMessage) -> str:
    time_prefix = f"{message['time']} " if message["time"] else ""
    return f"[{time_prefix}{message['speaker']}] {message['content']}"


def normalize_analyze_request(payload: AnalyzeRequest) -> NormalizedChat:
    """把两种前端入参统一成后续 AI 和数据库都能直接使用的 Python 数据。"""
    if payload.text is not None:
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="聊天原文不能为空")
        return {
            "source": "text",
            "text": text,
            "messages": [],
            "message_count": 0,
        }

    if not payload.messages:
        raise HTTPException(status_code=400, detail="聊天消息不能为空")

    messages = [
        _normalize_message(item, index)
        for index, item in enumerate(payload.messages, 1)
    ]
    return {
        "source": "messages",
        "text": "\n".join(_render_message(message) for message in messages),
        "messages": messages,
        "message_count": len(messages),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    """接收整段文本或逐条消息，统一后交给 AI 分析并保存。"""
    chat = normalize_analyze_request(payload)
    result = analyze_chat(chat["text"])
    record_id = database.save_record(chat["text"], result)
    return {"id": record_id, **result}


@app.get("/records")
def list_records() -> list:
    return database.list_records()


@app.get("/records/{record_id}")
def get_record(record_id: int) -> dict:
    record = database.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@app.put("/records/{record_id}")
def update_record(record_id: int, payload: SaveRequest) -> dict:
    record = database.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    result: dict[str, Any] = payload.result.model_dump(exclude_none=True)
    if "is_sample" not in result:
        result["is_sample"] = record["result"].get("is_sample", False)
    database.update_result(record_id, result)
    return {"ok": True}


@app.get("/records/{record_id}/export")
def export_record(record_id: int) -> JSONResponse:
    record = database.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return JSONResponse(
        content=record,
        headers={
            "Content-Disposition": f'attachment; filename="record-{record_id}.json"'
        },
    )
