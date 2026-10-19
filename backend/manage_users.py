"""Local-only account management. Passwords never appear in CLI arguments/logs."""

import argparse
import getpass
import os
from pathlib import Path
import secrets
import sqlite3

import auth
import auth_store
import database


def bootstrap_admins(usernames: list[str] | None = None) -> tuple[list[dict], Path]:
    """Create both admins transactionally and write credentials outside the repo."""
    names = ["keyoushu_admin1", "keyoushu_admin2"] if usernames is None else usernames
    if len(names) != 2 or len({name.casefold() for name in names}) != 2:
        raise ValueError("需要两个不同的管理员用户名")
    passwords = [secrets.token_urlsafe(24), secrets.token_urlsafe(24)]
    for name, password in zip(names, passwords):
        auth_store.validate_credentials(name, password)
    path = Path.home() / ".codex" / "local-credentials" / "keyoushu-admins.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    hashes = [auth_store.PASSWORD_HASH.hash(password) for password in passwords]
    fd = None
    created_file = False
    try:
        with database._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            role = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()
            if role is None:
                raise ValueError("请先执行数据库初始化")
            users = [auth_store._public(conn, auth_store._create(conn, name, hashed, [role[0]]))
                     for name, hashed in zip(names, hashes)]
            # Never overwrite a previous delivery, even when the DB was replaced.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created_file = True
            auth.restrict_private(path)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = None
                handle.write("客有数本机管理员凭据（请勿上传 GitHub 或转发）\n")
                handle.write("登录地址：http://127.0.0.1:5173/\n\n")
                for name, password in zip(names, passwords):
                    handle.write(f"账号：{name}\n密码：{password}\n\n")
                handle.flush()
                os.fsync(handle.fileno())
        return users, path
    except BaseException:
        if fd is not None:
            os.close(fd)
        if created_file:
            path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="客有数本机账号管理（密码仅交互输入）")
    parser.add_argument("command", nargs="?", choices=["create"])
    parser.add_argument("--username")
    parser.add_argument("--role", choices=["admin", "member", "viewer"], default="member")
    parser.add_argument("--bootstrap-admins", action="store_true")
    parser.add_argument("--usernames", nargs=2)
    args = parser.parse_args()
    database.init_db()
    try:
        if args.bootstrap_admins:
            if args.command or args.username:
                parser.error("bootstrap-admins 不能与 create/username 同时使用")
            users, path = bootstrap_admins(args.usernames)
            print("已创建管理员：" + ", ".join(user["username"] for user in users))
            print(f"凭据仅写入本机文件：{path}")
        elif args.command == "create" and args.username:
            password = getpass.getpass("密码（10–128 字符）：")
            if password != getpass.getpass("再次输入密码："):
                raise ValueError("两次密码不一致")
            user = auth_store.create_user(args.username, password, [args.role])
            print(f"已创建账号 {user['username']}，角色 {args.role}")
        else:
            parser.error("使用 create --username NAME --role admin 或 --bootstrap-admins")
    except FileExistsError:
        parser.exit(1, "已有本机管理员凭据文件；为防止覆盖，未创建或修改任何账号。\n")
    except sqlite3.IntegrityError:
        parser.exit(1, "用户名已存在；未创建或覆盖任何账号。\n")
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
