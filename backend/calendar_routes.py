"""Validated calendar endpoints using the existing live RBAC dependencies."""

import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

import calendar_store as store
from auth import permission

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def valid_date(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期须为 YYYY-MM-DD")
    date.fromisoformat(value)
    return value


class ItemCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    title: StrictStr = Field(min_length=1, max_length=200)
    notes: StrictStr = Field(default="", max_length=5000)
    due_date: StrictStr | None = None
    manual_level: StrictInt | None = Field(default=None, ge=1, le=5)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("标题不能为空")
        return value.strip()

    @field_validator("due_date")
    @classmethod
    def date_format(cls, value):
        return valid_date(value)


class ItemPatch(ItemCreate):
    title: StrictStr | None = Field(default=None, min_length=1, max_length=200)
    notes: StrictStr | None = Field(default=None, max_length=5000)

    @model_validator(mode="before")
    @classmethod
    def provided_non_null_fields(cls, value):
        if isinstance(value, dict):
            if not value:
                raise ValueError("至少修改一个字段")
            if any(key in value and value[key] is None for key in ("title", "notes")):
                raise ValueError("标题和备注不能为 null")
        return value


class Completion(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    completed: StrictBool


class RecordImport(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    record_id: StrictInt = Field(gt=0)
    task_index: StrictInt = Field(ge=0)
    expected_text: StrictStr = Field(min_length=1, max_length=5000)


def call(operation, *args, **kwargs):
    try:
        data = operation(*args, **kwargs)
    except store.CalendarError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    return {"code": 0, "message": "ok", "data": data}


@router.post("/items")
def create(payload: ItemCreate, user=Depends(permission("records:write"))):
    return call(store.create_item, user["id"], payload.model_dump())


@router.post("/items/from-record")
def from_record(payload: RecordImport, user=Depends(permission("records:write")),
                _reader=Depends(permission("records:read"))):
    return call(store.import_record_task, user, **payload.model_dump())


@router.get("/items")
def listing(from_date: str | None = Query(None, alias="from"),
            to_date: str | None = Query(None, alias="to"), scheduled: bool | None = None,
            status: Literal["open", "completed", "all"] = "open",
            limit: int = Query(500, ge=1, le=500), offset: int = Query(0, ge=0),
            user=Depends(permission("records:read"))):
    try:
        valid_date(from_date)
        valid_date(to_date)
    except ValueError:
        raise HTTPException(422, "日期须为有效的 YYYY-MM-DD") from None
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "查询开始日期不能晚于结束日期")
    if scheduled is False and (from_date or to_date):
        raise HTTPException(422, "无 DDL 待办不能按日历日期范围筛选")
    return call(store.list_items, user["id"], from_date=from_date, to_date=to_date,
                scheduled=scheduled, status=status, limit=limit, offset=offset)


@router.get("/items/{item_id}")
def get(item_id: int = Path(gt=0), user=Depends(permission("records:read"))):
    return call(store.get_item, user["id"], item_id)


@router.patch("/items/{item_id}")
def update(payload: ItemPatch, item_id: int = Path(gt=0), user=Depends(permission("records:write"))):
    return call(store.update_item, user["id"], item_id, payload.model_dump(exclude_unset=True))


@router.patch("/items/{item_id}/completion")
def completion(payload: Completion, item_id: int = Path(gt=0), user=Depends(permission("records:write"))):
    return call(store.complete_item, user["id"], item_id, payload.completed)


@router.delete("/items/{item_id}")
def delete(item_id: int = Path(gt=0), user=Depends(permission("records:write"))):
    return call(store.delete_item, user["id"], item_id)
