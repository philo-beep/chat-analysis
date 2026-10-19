"""SQLite users, RBAC, and revocable login sessions. No default credentials."""

import hashlib
import re
import sqlite3
import time

from pwdlib import PasswordHash

import database

PASSWORD_HASH = PasswordHash.recommended()
PERMISSIONS = {
    "analysis:run": "分析文本和截图", "records:read": "读取记录",
    "records:write": "修改记录", "records:export": "导出记录",
    "records:all": "访问所有用户及旧版记录", "users:read": "查看用户",
    "users:write": "管理用户和用户角色", "roles:read": "查看角色",
    "roles:write": "管理角色与角色权限", "permissions:read": "查看权限",
    "admin:stats": "查看后台访问和功能统计",
}
ROLE_GRANTS = {
    "admin": set(PERMISSIONS),
    "member": {"analysis:run", "records:read", "records:write", "records:export"},
    "viewer": {"records:read"},
}


def init_schema(conn: sqlite3.Connection) -> None:
    """Run inside the caller's migration transaction (no executescript commit)."""
    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(username) BETWEEN 3 AND 64),
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, created_at INTEGER NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL, created_at INTEGER NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
            created_at INTEGER NOT NULL, PRIMARY KEY(user_id, role_id))""",
        """CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE RESTRICT,
            created_at INTEGER NOT NULL, PRIMARY KEY(role_id, permission_id))""",
        """CREATE TABLE IF NOT EXISTS auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL, revoked_at INTEGER)""",
        "CREATE INDEX IF NOT EXISTS ix_user_roles_role ON user_roles(role_id, user_id)",
        "CREATE INDEX IF NOT EXISTS ix_role_permissions_permission ON role_permissions(permission_id, role_id)",
        "CREATE INDEX IF NOT EXISTS ix_auth_sessions_user ON auth_sessions(user_id, expires_at)",
        "CREATE INDEX IF NOT EXISTS ix_auth_sessions_expiry ON auth_sessions(expires_at)",
    ]
    for statement in statements:
        conn.execute(statement)
    now = int(time.time())
    for code, description in PERMISSIONS.items():
        conn.execute("INSERT OR IGNORE INTO permissions(code, description, created_at) VALUES(?,?,?)",
                     (code, description, now))
    for code, grants in ROLE_GRANTS.items():
        cur = conn.execute("INSERT OR IGNORE INTO roles(code,name,created_at) VALUES(?,?,?)",
                           (code, {"admin": "管理员", "member": "普通成员", "viewer": "只读成员"}[code], now))
        if cur.rowcount:  # Never restore privileges deliberately changed by an operator.
            role_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO role_permissions(role_id,permission_id,created_at) "
                "SELECT ?,id,? FROM permissions WHERE code=?",
                [(role_id, now, permission) for permission in sorted(grants)],
            )


def validate_credentials(username: str, password: str) -> None:
    if not isinstance(username, str) or not re.fullmatch(r"[\w.-]{3,64}", username):
        raise ValueError("用户名须为 3–64 位字母、数字、汉字、下划线、点或短横线")
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise ValueError("密码长度须为 10–128 个字符")


def _public(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute("SELECT id,username,is_active,created_at,updated_at FROM users WHERE id=?",
                       (user_id,)).fetchone()
    if row is None:
        return None
    user = dict(row)
    user["is_active"] = bool(user["is_active"])
    user["roles"] = [r[0] for r in conn.execute(
        "SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id=r.id "
        "WHERE ur.user_id=? ORDER BY r.code", (user_id,))]
    user["permissions"] = [r[0] for r in conn.execute(
        "SELECT DISTINCT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id "
        "JOIN user_roles ur ON ur.role_id=rp.role_id WHERE ur.user_id=? ORDER BY p.code", (user_id,))]
    return user


def public_user(user_id: int) -> dict | None:
    with database._connect() as conn:
        return _public(conn, user_id)


def _validate_ids(conn: sqlite3.Connection, table: str, ids: list[int]) -> None:
    if table not in {"roles", "permissions"}:
        raise ValueError("无效关联表")
    if len(ids) != len(set(ids)) or any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError("关联 ID 必须是无重复的正整数")
    if ids:
        count = conn.execute(f"SELECT count(*) FROM {table} WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchone()[0]
        if count != len(ids):
            raise ValueError("角色或权限 ID 不存在；未保存任何变更")


def _create(conn: sqlite3.Connection, username: str, password_hash: str, role_ids: list[int]) -> int:
    _validate_ids(conn, "roles", role_ids)
    now = int(time.time())
    cur = conn.execute("INSERT INTO users(username,password_hash,created_at,updated_at) VALUES(?,?,?,?)",
                       (username, password_hash, now, now))
    user_id = int(cur.lastrowid)
    conn.executemany("INSERT INTO user_roles(user_id,role_id,created_at) VALUES(?,?,?)",
                     [(user_id, role_id, now) for role_id in role_ids])
    return user_id


def create_user(username: str, password: str, role_codes: list[str] | None = None) -> dict:
    validate_credentials(username, password)
    codes = ["member"] if role_codes is None else role_codes
    if len(codes) != len(set(codes)):
        raise ValueError("角色不可重复")
    hashed = PASSWORD_HASH.hash(password)
    with database._connect() as conn:
        role_ids = []
        for code in codes:
            role = conn.execute("SELECT id FROM roles WHERE code=?", (code,)).fetchone()
            if role is None:
                raise ValueError("角色不存在")
            role_ids.append(role[0])
        return _public(conn, _create(conn, username, hashed, role_ids))


def create_user_with_roles(username: str, password: str, role_ids: list[int]) -> dict:
    validate_credentials(username, password)
    hashed = PASSWORD_HASH.hash(password)
    with database._connect() as conn:
        return _public(conn, _create(conn, username, hashed, role_ids))


def verify_credentials(username: str, password: str) -> dict | None:
    with database._connect() as conn:
        row = conn.execute("SELECT id,password_hash,is_active FROM users WHERE username=?", (username,)).fetchone()
    # Always run Argon2, including unknown users, to reduce username timing disclosure.
    stored_hash = row["password_hash"] if row else _dummy_hash()
    try:
        valid = PASSWORD_HASH.verify(password, stored_hash)
    except (ValueError, TypeError):
        valid = False
    if not row or not valid or not row["is_active"]:
        return None
    return public_user(row["id"])


_DUMMY_HASH = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = PASSWORD_HASH.hash("unknown-user-dummy-password")
    return _DUMMY_HASH


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def save_session(user_id: int, token: str, created_at: int, expires_at: int) -> None:
    with database._connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (created_at - 86400,))
        conn.execute("INSERT INTO auth_sessions(user_id,token_hash,created_at,expires_at) VALUES(?,?,?,?)",
                     (user_id, token_hash(token), created_at, expires_at))


def session_user(user_id: int, token: str) -> dict | None:
    with database._connect() as conn:
        row = conn.execute("SELECT id FROM auth_sessions WHERE user_id=? AND token_hash=? "
                           "AND revoked_at IS NULL AND expires_at>?", (user_id, token_hash(token), int(time.time()))).fetchone()
        user = _public(conn, user_id) if row else None
        return user if user and user["is_active"] else None


def revoke_session(token: str) -> None:
    with database._connect() as conn:
        conn.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                     (int(time.time()), token_hash(token)))


def list_users(limit: int = 50, offset: int = 0) -> dict:
    with database._connect() as conn:
        total = conn.execute("SELECT count(*) FROM users").fetchone()[0]
        ids = conn.execute("SELECT id FROM users ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return {"items": [_public(conn, row[0]) for row in ids], "total": total, "limit": limit, "offset": offset}


def list_roles() -> list[dict]:
    with database._connect() as conn:
        roles = []
        for row in conn.execute("SELECT id,code,name,created_at FROM roles ORDER BY id"):
            role = dict(row)
            role["permission_ids"] = [p[0] for p in conn.execute(
                "SELECT permission_id FROM role_permissions WHERE role_id=? ORDER BY permission_id", (row["id"],))]
            roles.append(role)
        return roles


def list_permissions() -> list[dict]:
    with database._connect() as conn:
        return [dict(row) for row in conn.execute("SELECT id,code,description FROM permissions ORDER BY id")]


def create_role(code: str, name: str) -> dict:
    with database._connect() as conn:
        cur = conn.execute("INSERT INTO roles(code,name,created_at) VALUES(?,?,?)", (code, name, int(time.time())))
        return {"id": cur.lastrowid, "code": code, "name": name, "permission_ids": []}


def set_role_permissions(role_id: int, permission_ids: list[int]) -> dict:
    with database._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        role = conn.execute("SELECT code FROM roles WHERE id=?", (role_id,)).fetchone()
        if role is None:
            raise LookupError("角色不存在")
        _validate_ids(conn, "permissions", permission_ids)
        if role["code"] == "admin":
            required = {r[0] for r in conn.execute("SELECT id FROM permissions WHERE code IN (" + ','.join('?' for _ in PERMISSIONS) + ')', list(PERMISSIONS))}
            if not required.issubset(set(permission_ids)):
                raise ValueError("内置管理员角色必须保留全部系统权限")
        conn.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
        conn.executemany("INSERT INTO role_permissions(role_id,permission_id,created_at) VALUES(?,?,?)",
                         [(role_id, permission_id, int(time.time())) for permission_id in permission_ids])
        return {"id": role_id, "permission_ids": sorted(permission_ids)}


def _ensure_admin_survives(conn: sqlite3.Connection, user_id: int, *, role_ids: list[int] | None = None, active: bool | None = None) -> None:
    user = _public(conn, user_id)
    if user is None:
        raise LookupError("用户不存在")
    if not user["is_active"] or "admin" not in user["roles"]:
        return
    admin_id = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()[0]
    loses_admin = active is False or (role_ids is not None and admin_id not in role_ids)
    if loses_admin:
        count = conn.execute("SELECT count(*) FROM users u JOIN user_roles ur ON ur.user_id=u.id "
                             "WHERE u.is_active=1 AND ur.role_id=? AND u.id<>?", (admin_id, user_id)).fetchone()[0]
        if count == 0:
            raise ValueError("不能停用或降级最后一位有效管理员")


def set_user_roles(user_id: int, role_ids: list[int]) -> dict:
    with database._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_ids(conn, "roles", role_ids)
        _ensure_admin_survives(conn, user_id, role_ids=role_ids)
        conn.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
        conn.executemany("INSERT INTO user_roles(user_id,role_id,created_at) VALUES(?,?,?)",
                         [(user_id, role_id, int(time.time())) for role_id in role_ids])
        conn.execute("UPDATE users SET updated_at=? WHERE id=?", (int(time.time()), user_id))
        return _public(conn, user_id)


def set_user_active(user_id: int, active: bool) -> dict:
    with database._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_admin_survives(conn, user_id, active=active)
        now = int(time.time())
        conn.execute("UPDATE users SET is_active=?,updated_at=? WHERE id=?", (int(active), now, user_id))
        if not active:
            conn.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, user_id))
        return _public(conn, user_id)
