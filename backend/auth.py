"""JWT authentication and centralized, live database permission checks."""

import getpass
import os
from pathlib import Path
import secrets
import subprocess
import time

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import auth_store

TOKEN_TTL = 3600
ISSUER = "keyoushu"
AUDIENCE = "keyoushu-web"
_bearer = HTTPBearer(auto_error=False)


def restrict_private(path: Path) -> None:
    """Credentials must only be readable by the current local user."""
    if os.name == "nt":
        account = getpass.getuser()
        domain = os.environ.get("USERDOMAIN")
        if domain:
            account = domain + "\\" + account
        result = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:(F)"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise RuntimeError("无法限制本机凭据文件访问权限，请检查文件 ACL")
    else:
        path.chmod(0o600)


def signing_secret() -> str:
    configured = os.environ.get("KEYOUSHU_JWT_SECRET")
    if configured is not None:
        if len(configured) < 32:
            raise RuntimeError("KEYOUSHU_JWT_SECRET 至少需要 32 个字符")
        return configured
    path = Path.home() / ".codex" / "local-credentials" / "keyoushu-jwt.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        try:
            # Restrict before writing any secret bytes on Windows.
            restrict_private(path)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(secrets.token_urlsafe(48))
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            path.unlink(missing_ok=True)
            raise
    # A second worker can observe the exclusively created file before its writer flushes.
    for _ in range(50):
        value = path.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
        time.sleep(0.01)
    raise RuntimeError("本机 JWT 签名密钥无效；请检查 keyoushu-jwt.key")


def issue_token(user: dict) -> str:
    now = int(time.time())
    token = jwt.encode({"sub": str(user["id"]), "jti": secrets.token_urlsafe(24),
                        "iat": now, "exp": now + TOKEN_TTL, "iss": ISSUER, "aud": AUDIENCE},
                       signing_secret(), algorithm="HS256")
    auth_store.save_session(user["id"], token, now, now + TOKEN_TTL)
    return token


def unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="请先登录或重新登录", headers={"WWW-Authenticate": "Bearer"})


def require_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    token = credentials.credentials
    if len(token) > 4096:
        raise unauthorized()
    try:
        claims = jwt.decode(token, signing_secret(), algorithms=["HS256"], audience=AUDIENCE,
                            issuer=ISSUER, options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]})
        if not isinstance(claims["sub"], str) or not claims["sub"].isdigit():
            raise unauthorized()
        if not isinstance(claims["jti"], str) or not claims["jti"]:
            raise unauthorized()
        user = auth_store.session_user(int(claims["sub"]), token)
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
        raise unauthorized()
    if user is None:
        raise unauthorized()
    request.state.user = user
    request.state.auth_token = token
    return user


def permission(code: str):
    if code not in auth_store.PERMISSIONS:
        raise ValueError("未声明的权限代码")

    def check(user: dict = Depends(require_user)) -> dict:
        if code not in user["permissions"]:
            raise HTTPException(status_code=403, detail="没有执行此操作的权限")
        return user

    return check


def administration_permission(code: str):
    """Management mutations require both permission and the built-in admin role.

    Custom roles may receive read/write permission codes for application use,
    but cannot grant themselves higher privileges through RBAC administration.
    """
    def check(user: dict = Depends(permission(code))) -> dict:
        if "admin" not in user["roles"]:
            raise HTTPException(status_code=403, detail="仅内置管理员可以修改用户、角色或权限")
        return user

    return check
