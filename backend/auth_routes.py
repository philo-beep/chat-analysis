"""Public member registration and token session endpoints."""

from collections import defaultdict, deque
import sqlite3
from threading import Lock
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictStr

import auth
import auth_store
import database

router = APIRouter(prefix="/api/auth", tags=["认证"])


class RegisterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: StrictStr = Field(min_length=3, max_length=64, pattern=r"^[\w.-]+$")
    password: StrictStr = Field(min_length=10, max_length=128)


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: StrictStr = Field(min_length=1, max_length=64)
    password: StrictStr = Field(min_length=1, max_length=128)


def ok(data=None, message="成功") -> dict:
    return {"code": 0, "message": message, "data": data}


_attempts = defaultdict(deque)
_limit_lock = Lock()
_WINDOW = 300


def _rate_keys(request: Request, username: str, action: str) -> list[tuple]:
    # Trust the socket peer only: spoofed X-Forwarded-For must not bypass limits.
    peer = request.client.host if request.client else "local"
    db = str(database.DB_PATH.resolve())
    return [(db, action, peer), (db, action, peer, username.casefold())]


def _begin_attempt(request: Request, username: str, action: str) -> list[tuple]:
    keys = _rate_keys(request, username, action)
    now = time.monotonic()
    with _limit_lock:
        for key in list(_attempts):
            queue = _attempts[key]
            while queue and queue[0] <= now - _WINDOW:
                queue.popleft()
            if not queue:
                del _attempts[key]
        for index, key in enumerate(keys):
            limit = 30 if index == 0 else 10
            if len(_attempts[key]) >= limit:
                raise HTTPException(429, "请求过于频繁，请 5 分钟后重试", headers={"Retry-After": "300"})
        for key in keys:
            _attempts[key].append(now)
    return keys


def _successful_login(keys: list[tuple]) -> None:
    with _limit_lock:
        # Keep IP-wide history to prevent successful accounts bypassing abuse controls.
        _attempts.pop(keys[-1], None)


@router.post("/register")
def register(body: RegisterBody, request: Request):
    _begin_attempt(request, body.username, "register")
    try:
        user = auth_store.create_user(body.username, body.password, ["member"])
    except sqlite3.IntegrityError:
        raise HTTPException(409, "用户名已存在，请更换用户名。")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    request.state.user = user
    return ok({"user": user}, "注册成功，请登录")


@router.post("/login")
def login(body: LoginBody, request: Request):
    keys = _begin_attempt(request, body.username, "login")
    user = auth_store.verify_credentials(body.username, body.password)
    if user is None:
        raise HTTPException(401, "用户名或密码错误，或账号已停用", headers={"WWW-Authenticate": "Bearer"})
    token = auth.issue_token(user)
    _successful_login(keys)
    request.state.user = user
    return ok({"token": token, "token_type": "bearer", "expires_in": auth.TOKEN_TTL, "user": user}, "登录成功")


@router.get("/me")
def me(user: dict = Depends(auth.require_user)):
    return ok(user)


@router.post("/logout")
def logout(request: Request, user: dict = Depends(auth.require_user)):
    auth_store.revoke_session(request.state.auth_token)
    return ok(None, "已退出登录")
