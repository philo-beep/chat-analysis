"""接口入口，C 负责。

接口约定见 docs/api.md，字段名称 / 数据类型 / 空值规则都要固定。
"""

import base64
import io
import logging
import sqlite3
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

import database
import audit
import profile_store
from auth import permission
from auth_routes import router as auth_router
from access_routes import router as access_router
from calendar_routes import router as calendar_router
from customer_routes import router as customer_router
from ai_service import analyze_chat
from ai_contract import AnalysisOutcome
from analysis_models import AIOutput, RecordResult, RequirementModel, SaveRequest, AnalysisAction
from ai_service import ConfigurationError, ModelAPIError, InvalidModelOutput

# 读 backend/.env（复制 .env.example 得到）。密钥只在本机，不进仓库。
load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger("keyoushu.backend")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="聊天分析 API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(access_router)
app.include_router(calendar_router)
app.include_router(customer_router)
app.include_router(audit.routes())
app.middleware('http')(audit.record_request)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    content = ({'code': exc.status_code, 'message': str(exc.detail), 'data': None}
               if request.url.path.startswith('/api/') else {'detail': exc.detail})
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Never echo password/token inputs from Pydantic errors.
    details = [{'loc': list(e['loc']), 'type': e['type'], 'msg': e['msg']} for e in exc.errors()]
    content = ({'code': 422, 'message': '输入格式不正确，请检查字段及长度', 'data': None}
               if request.url.path.startswith('/api/') else {'detail': details})
    return JSONResponse(status_code=422, content=content)

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

    model_config = ConfigDict(strict=True, extra="forbid")

    speaker: StrictStr | None = Field(None, description="显示名称，例如：客户、商家")
    role: StrictStr | None = Field(None, description="角色，例如：customer、seller")
    content: StrictStr | None = Field(None, description="消息内容")
    text: StrictStr | None = Field(None, description="消息内容的兼容写法")
    time: StrictStr | None = Field(None, description="消息时间，可选")
    timestamp: StrictStr | None = Field(None, description="消息时间的兼容写法")


class AnalyzeRequest(BaseModel):
    """保留既有 text / messages 两种 JSON 输入。"""

    model_config = ConfigDict(strict=True, extra="forbid")

    text: StrictStr | None = Field(None, description="聊天原文（含客户名称）")
    messages: list[ChatMessageIn | StrictStr] | None = None

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


ResultModel = RecordResult


@app.exception_handler(sqlite3.Error)
async def database_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
    logger.error(
        "数据库操作失败: %s %s", request.method, request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=({'code':500,'message':'数据库操作失败，请检查服务端日志','data':None}
                 if request.url.path.startswith('/api/') else {"detail": "数据库操作失败，请联系 C 检查服务端日志"}),
    )


@app.exception_handler(database.RecordDataError)
async def record_data_error(request: Request, exc: database.RecordDataError) -> JSONResponse:
    logger.error(
        "历史记录损坏: %s %s", request.method, request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=({'code':500,'message':'历史记录内容损坏，请检查服务端日志','data':None}
                 if request.url.path.startswith('/api/') else {"detail": "历史记录内容损坏，请联系 C 检查服务端日志"}),
    )


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

    content = (item.content if item.content is not None else item.text or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail=f"第 {index} 条消息不能为空")

    speaker = (item.speaker or "").strip()
    role = _normalize_role(item.role, speaker)
    message_time = (item.time if item.time is not None else item.timestamp or "").strip() or None
    return {
        "role": role,
        "speaker": speaker or _ROLE_LABELS.get(role, "未标注"),
        "content": content,
        "time": message_time,
    }


def _render_message(message: NormalizedMessage) -> str:
    time_prefix = f"{message['time']} " if message["time"] else ""
    role_label = _ROLE_LABELS.get(message["role"])
    speaker = message["speaker"]
    if role_label and speaker != role_label:
        speaker = f"{role_label}({speaker})"
    return f"[{time_prefix}{speaker}] {message['content']}"


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


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_IMAGE_BYTES + 64 * 1024
MAX_IMAGE_PIXELS = 25_000_000
IMAGE_MIMES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def analyze_chat_with_source(text: str, image_bytes: bytes, image_mime: str, *, profile_resolver=None) -> AnalysisOutcome:
    """D 的截图入口延迟导入，文本服务不依赖截图模型加载。"""
    import ai_service

    handler = getattr(ai_service, "analyze_chat_with_source", None)
    if handler is None:
        raise NotImplementedError("本地截图模型尚未接入")
    return handler(text, image_bytes, image_mime, profile_resolver=profile_resolver)


def validate_image(image_bytes: bytes, declared_mime: str | None) -> str:
    if not image_bytes:
        raise HTTPException(status_code=400, detail="聊天截图不能为空")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="聊天截图不能超过 10 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as image:
                mime = IMAGE_MIMES.get(image.format)
                if not mime:
                    raise HTTPException(status_code=415, detail="聊天截图只支持 PNG、JPG、WebP")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(status_code=413, detail="聊天截图像素过多，请缩小后重试")
                image.verify()
            # verify 检查文件结构，load 检查实际压缩图像能否完整解码。
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise HTTPException(status_code=400, detail="聊天截图损坏或不是有效图片") from None
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=413, detail="聊天截图像素过多，请缩小后重试") from None
    normalized_mime = "image/jpeg" if declared_mime == "image/jpg" else declared_mime
    if normalized_mime not in (None, "application/octet-stream", mime):
        raise HTTPException(status_code=415, detail="图片内容与声明格式不一致")
    return mime


def _analyze_and_save(
    model_text: str, original_text: str, source_input: dict,
    image_bytes: bytes | None = None, image_mime: str | None = None,
    owner_id: int | None = None,
) -> dict:
    source_transcript = ""
    resolved = {}

    def resolve_profile(identity):
        context = profile_store.context_for_identity(owner_id, identity)
        resolved['context'] = context
        return context if context.get('profile') is not None else None

    try:
        if image_bytes is None:
            raw_result = analyze_chat(model_text, profile_resolver=resolve_profile)
        else:
            outcome = analyze_chat_with_source(model_text, image_bytes, image_mime, profile_resolver=resolve_profile)
            if not isinstance(outcome, AnalysisOutcome) or not isinstance(outcome.source_text, str):
                raise ValueError("截图模型返回的内部结果不符合约定")
            source_transcript = outcome.source_text
            if not source_transcript.strip():
                raise ValueError("截图模型没有返回可核对的转录")
            raw_result = outcome.result
    except NotImplementedError:
        logger.exception("模型尚未接入")
        raise HTTPException(status_code=500, detail="真实模型调用尚未实现，请联系 D 完成接入") from None
    except (ConfigurationError, ModelAPIError, InvalidModelOutput) as exc:
        # These classes contain only curated, credential-free messages.
        logger.warning("分析服务失败：%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except TimeoutError:
        logger.exception("模型调用超时")
        raise HTTPException(status_code=500, detail="模型调用超时，请稍后重试") from None
    except Exception:
        logger.exception("模型调用失败")
        raise HTTPException(status_code=500, detail="模型调用失败，请稍后重试；持续失败请联系 D") from None

    profile = None
    expanded = isinstance(raw_result, dict) and any(key in raw_result for key in ('customer_profile', 'ddl_tasks', 'suggested_tasks'))
    try:
        if expanded:
            model_output = AIOutput.model_validate({key: value for key, value in raw_result.items() if key != 'is_sample'})
            values = model_output.model_dump()
            profile = values.pop('customer_profile')
            values.update(analysis_version=2, is_sample=False, action_states={})
            values['questions'] = [{**question, 'status': 'pending', 'confirmed_answer': None}
                                   for question in values['questions']]
            validated = ResultModel.model_validate(values)
        else:
            validated = ResultModel.model_validate(raw_result)
    except ValidationError as exc:
        logger.warning("模型结果字段校验失败，共 %s 处错误", exc.error_count())
        raise HTTPException(status_code=500, detail="模型返回结果格式不符合接口约定，请联系 D 检查") from None

    source_text = original_text
    if image_bytes is not None:
        source_text += ("\n\n" if source_text else "") + "[聊天截图转录]\n" + source_transcript
    # 截图证据来自已保存的转录；原图片一同保存，供人工核对转录。
    if not validated.is_sample and any(
        item.evidence not in source_text for item in validated.requirements
    ):
        logger.warning("模型结果包含无法在原文中找到的引用")
        raise HTTPException(status_code=500, detail="模型返回的原文引用无效，请联系 D 检查")

    result = validated.model_dump(exclude_unset=True)
    result.setdefault('is_sample', False)
    if expanded and any(task['source_quote'] not in source_text for task in result['ddl_tasks']):
        raise HTTPException(status_code=502, detail='任务来源无法在原文中找到，请重试')
    source_image = None
    if image_bytes is not None:
        source_image = f"data:{image_mime};base64," + base64.b64encode(image_bytes).decode("ascii")
    try:
        record_id = database.save_record(
            source_text, result, source_input=source_input,
            source_image=source_image, source_transcript=source_transcript, owner_id=owner_id,
            customer_profile=profile,
            **({'profile_context': resolved['context']} if 'context' in resolved else {}),
        )
    except profile_store.ProfileConflictError:
        raise HTTPException(status_code=409, detail='这位客户刚有新的整理结果，本次尚未保存，请重新整理以合并最新资料') from None
    return {"id": record_id, **result}


@app.post("/analyze", openapi_extra={
    "requestBody": {"required": True, "content": {
        "application/json": {"schema": {"oneOf": [
            {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            {"type": "object", "required": ["messages"], "properties": {"messages": {
                "type": "array", "items": {"oneOf": [{"type": "string"}, {"type": "object"}]},
            }}},
        ]}},
        "multipart/form-data": {"schema": {"type": "object", "required": ["image"], "properties": {
            "text": {"type": "string"}, "image": {"type": "string", "format": "binary"},
        }}},
    }},
})
async def analyze(request: Request, user=Depends(permission('analysis:run'))) -> dict:
    """Keep original inputs; expanded results never expose the customer profile."""
    size = 0
    chunks = []
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="请求过大，聊天截图不能超过 10 MiB")
        chunks.append(chunk)
    request._body = b"".join(chunks)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type == "multipart/form-data":
        try:
            async with request.form(max_files=1, max_fields=2) as form:
                if (set(form) - {"text", "image"} or len(form.getlist("text")) > 1
                        or len(form.getlist("image")) > 1):
                    raise HTTPException(status_code=422, detail="表单只接受一个 text 和一个 image")
                original_text = form.get("text", "")
                image = form.get("image")
                if not isinstance(original_text, str) or not isinstance(image, UploadFile):
                    raise HTTPException(status_code=422, detail="请提供 text 字符串和 image 图片文件")
                image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
                image_mime = await run_in_threadpool(validate_image, image_bytes, image.content_type)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="图片表单无法读取，请重新上传") from None
        return await run_in_threadpool(
            _analyze_and_save, original_text.strip(), original_text,
            {"text": original_text}, image_bytes, image_mime, user['id'],
        )
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="请使用 JSON 文本或 multipart 图片表单")
    try:
        original_payload = await request.json()
        payload = AnalyzeRequest.model_validate(original_payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None
    except ValueError:
        raise HTTPException(status_code=400, detail="请求不是有效 JSON") from None
    chat = normalize_analyze_request(payload)
    original_text = payload.text if payload.text is not None else chat["text"]
    return await run_in_threadpool(
        _analyze_and_save, chat["text"], original_text,
        original_payload, owner_id=user['id'],
    )


@app.get("/records")
def list_records(user=Depends(permission('records:read'))) -> list:
    return database.list_records(**_scope(user))


@app.get("/records/{record_id}")
def get_record(record_id: int, user=Depends(permission('records:read'))) -> dict:
    record = database.get_record(record_id, **_scope(user))
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


def delete_record(record_id: int, user) -> dict:
    import calendar_store

    deleted = calendar_store.delete_owned_record_and_tasks(record_id, user['id'])
    if deleted is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return deleted


@app.delete("/records/{record_id}")
def delete_record_route(record_id: int, user=Depends(permission('records:write'))) -> dict:
    return delete_record(record_id, user)


@app.put("/records/{record_id}")
def update_record(record_id: int, payload: SaveRequest, user=Depends(permission('records:write'))) -> dict:
    record = database.get_record(record_id, **_scope(user))
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    result = payload.result.model_dump(exclude={"is_sample"}, exclude_unset=True)
    # 来源标记由分析时确定，编辑请求不能把开发样例改成真实模型结果。
    # 对没有来源标记的旧记录保留缺失状态，不擅自判断其来源。
    if "is_sample" in record["result"]:
        result["is_sample"] = record["result"]["is_sample"]
    import calendar_store
    try:
        if not database.update_result(record_id, result, **_scope(user)):
            raise HTTPException(status_code=404, detail="记录不存在")
    except calendar_store.CalendarError as exc:
        raise HTTPException(exc.status, exc.message) from None
    return {"ok": True}


@app.post('/api/records/{record_id}/actions')
def analysis_action(record_id: int, payload: AnalysisAction,
                    user=Depends(permission('records:write')),
                    _reader=Depends(permission('records:read'))):
    from record_actions import apply_action
    import calendar_store
    try:
        result = apply_action(user, record_id, payload.model_dump())
    except calendar_store.CalendarError as exc:
        raise HTTPException(exc.status, exc.message) from None
    return {'code': 0, 'message': '操作已保存', 'data': result}


@app.get("/records/{record_id}/export")
def export_record(record_id: int, user=Depends(permission('records:export'))) -> JSONResponse:
    record = database.get_record(record_id, **_scope(user))
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return JSONResponse(
        content=record,
        headers={
            "Content-Disposition": f'attachment; filename="record-{record_id}.json"'
        },
    )


def _scope(user):
    """Every HTTP record operation supplies an explicit server-trusted scope."""
    return {'owner_id': user['id'], 'include_all': 'records:all' in user['permissions']}


@app.post('/api/analyze')
async def api_analyze(request: Request, user=Depends(permission('analysis:run'))):
    return {'code':0,'message':'分析成功','data':await analyze(request, user)}


@app.get('/api/records')
def api_records(user=Depends(permission('records:read'))):
    return {'code':0,'message':'ok','data':database.list_records(**_scope(user), viewer_id=user['id'])}


@app.get('/api/records/{record_id}')
def api_record(record_id: int, user=Depends(permission('records:read'))):
    return {'code':0,'message':'ok','data':get_record(record_id,user)}


@app.delete('/api/records/{record_id}')
def api_delete_record(record_id: int, user=Depends(permission('records:write'))):
    return {'code':0,'message':'已删除聊天及其同步日历任务','data':delete_record(record_id,user)}


@app.put('/api/records/{record_id}')
def api_update_record(record_id: int, payload: SaveRequest, user=Depends(permission('records:write'))):
    return {'code':0,'message':'保存成功','data':update_record(record_id,payload,user)}


@app.get('/api/records/{record_id}/export')
def api_export_record(record_id: int, user=Depends(permission('records:export'))):
    return {'code':0,'message':'ok','data':get_scoped_export(record_id,user)}


def get_scoped_export(record_id,user):
    record=database.get_record(record_id,**_scope(user))
    if record is None:
        raise HTTPException(404,'记录不存在')
    return record
