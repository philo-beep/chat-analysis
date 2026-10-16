"""接口入口，C 负责。

接口约定见 docs/api.md，字段名称 / 数据类型 / 空值规则都要固定。
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import database
from ai_service import analyze_chat

app = FastAPI(title="聊天分析 API", version="0.1.0")

# 开发阶段允许前端本地地址跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="聊天原文")


class ResultModel(BaseModel):
    requirements: list = []
    questions: list = []
    tasks: list = []
    reply: str = ""


class SaveRequest(BaseModel):
    result: ResultModel


@app.on_event("startup")
def _startup() -> None:
    database.init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    """输入聊天原文，返回需求、待确认问题、建议待办、回复草稿。"""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="聊天原文不能为空")

    result = analyze_chat(payload.text)
    record_id = database.save_record(payload.text, result)
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
    if database.get_record(record_id) is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    database.update_result(record_id, payload.result.model_dump())
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
