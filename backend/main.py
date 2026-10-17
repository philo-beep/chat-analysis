"""接口入口，C 负责。

接口约定见 docs/api.md，字段名称 / 数据类型 / 空值规则都要固定。
"""

import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError

import database
from ai_service import analyze_chat

# 读 backend/.env（复制 .env.example 得到）。密钥只在本机，不进仓库。
load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger("keyoushu.backend")


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


class AnalyzeRequest(BaseModel):
    text: StrictStr = Field(..., description="聊天原文（含客户名称）")


class RequirementModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    field: StrictStr = Field(min_length=1, pattern=r"\S")
    value: StrictStr = Field(min_length=1, pattern=r"\S")
    evidence: StrictStr = Field(min_length=1, pattern=r"\S")


class ResultModel(BaseModel):
    # 兼容前端将 /analyze 的整个响应（含 id）作为 result 回传。
    # 未声明的展示元数据不写入数据库，四个业务字段必须完整提供。
    model_config = ConfigDict(strict=True)

    requirements: list[RequirementModel]
    questions: list[StrictStr]
    tasks: list[StrictStr]
    reply: StrictStr
    is_sample: StrictBool = False


class SaveRequest(BaseModel):
    result: ResultModel


@app.exception_handler(sqlite3.Error)
async def database_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
    logger.error(
        "数据库操作失败: %s %s", request.method, request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "数据库操作失败，请联系 C 检查服务端日志"},
    )


@app.exception_handler(database.RecordDataError)
async def record_data_error(request: Request, exc: database.RecordDataError) -> JSONResponse:
    logger.error(
        "历史记录损坏: %s %s", request.method, request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "历史记录内容损坏，请联系 C 检查服务端日志"},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    """输入聊天原文，返回需求、待确认问题、建议待办、回复草稿。"""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="聊天原文不能为空")

    try:
        raw_result = analyze_chat(payload.text.strip())
    except NotImplementedError:
        logger.exception("模型尚未接入")
        raise HTTPException(status_code=500, detail="真实模型调用尚未实现，请联系 D 完成接入") from None
    except TimeoutError:
        logger.exception("模型调用超时")
        raise HTTPException(status_code=500, detail="模型调用超时，请稍后重试") from None
    except Exception:
        logger.exception("模型调用失败")
        raise HTTPException(status_code=500, detail="模型调用失败，请稍后重试；持续失败请联系 D") from None

    try:
        validated = ResultModel.model_validate(raw_result)
    except ValidationError as exc:
        logger.warning("模型结果字段校验失败，共 %s 处错误", exc.error_count())
        raise HTTPException(status_code=500, detail="模型返回结果格式不符合接口约定，请联系 D 检查") from None

    # 开发样例显著标注为假数据；真实分析的每条依据必须出自输入原文。
    if not validated.is_sample and any(
        item.evidence not in payload.text for item in validated.requirements
    ):
        logger.warning("模型结果包含无法在原文中找到的引用")
        raise HTTPException(status_code=500, detail="模型返回的原文引用无效，请联系 D 检查")

    result = validated.model_dump()
    # 保存完整原始输入，分析时忽略首尾空白，不丢失核对原文所需的信息。
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
    record = database.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    result = payload.result.model_dump(exclude={"is_sample"})
    # 来源标记由分析时确定，编辑请求不能把开发样例改成真实模型结果。
    # 对没有来源标记的旧记录保留缺失状态，不擅自判断其来源。
    if "is_sample" in record["result"]:
        result["is_sample"] = record["result"]["is_sample"]
    if not database.update_result(record_id, result):
        raise HTTPException(status_code=404, detail="记录不存在")
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
