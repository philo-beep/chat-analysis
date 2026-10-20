"""数据保存，C 负责。

本地 SQLite，数据库文件不进仓库（见 .gitignore）。
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).parent / "app.db"


class RecordDataError(Exception):
    """历史记录中的结果不是可读取的 JSON 对象。"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        with conn:
            yield conn
    finally:
        # sqlite3.Connection 自身的上下文管理器只提交/回滚，不会关闭连接。
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        from auth_store import init_schema
        import audit
        init_schema(conn)
        audit.init_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(records)")}
        for name, declaration in {
            "source_input": "TEXT",
            "source_image": "TEXT",
            "source_transcript": "TEXT NOT NULL DEFAULT ''",
            "owner_id": "INTEGER REFERENCES users(id)",
        }.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE records ADD COLUMN {name} {declaration}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_owner ON records(owner_id, id DESC)")
        from calendar_store import init_schema as init_calendar_schema
        init_calendar_schema(conn)
        from profile_store import init_schema as init_profile_schema
        init_profile_schema(conn)
        marker = conn.execute("SELECT 1 FROM calendar_migrations WHERE code='record-task-backfill-v1'").fetchone()
        if marker is None:
            from calendar_store import sync_existing_record_tasks
            sync_existing_record_tasks(conn)
            conn.execute("INSERT INTO calendar_migrations (code,applied_at) VALUES ('record-task-backfill-v1',?)",
                         (datetime.now().astimezone().isoformat(timespec="seconds"),))


def save_record(
    text: str, result: dict, *, source_input: dict | None = None,
    source_image: str | None = None, source_transcript: str = "",
    owner_id: int | None = None,
    customer_profile: dict | None = None,
) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    title = text.strip().splitlines()[0][:30] if text.strip() else "未命名"
    # Private profiles must never enter records.result or the public export path.
    result = dict(result)
    embedded_profile = result.pop("customer_profile", None)
    if customer_profile is None:
        customer_profile = embedded_profile
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "INSERT INTO records (title, text, result, created_at, updated_at,"
            " source_input, source_image, source_transcript, owner_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, text, json.dumps(result, ensure_ascii=False), now, now,
             json.dumps(source_input, ensure_ascii=False) if source_input is not None else None,
             source_image, source_transcript, owner_id),
        )
        record_id = int(cur.lastrowid)
        from calendar_store import sync_record_tasks
        sync_record_tasks(conn, owner_id, record_id, result)
        from profile_store import save_snapshot
        save_snapshot(conn, owner_id, record_id, customer_profile)
        return record_id


def list_records(*, owner_id: int | None = None, include_all: bool = True,
                 viewer_id: int | None = None) -> list[dict]:
    fields = "id, title, created_at, updated_at"
    args: tuple = ()
    if viewer_id is not None:
        fields += ", (owner_id = ?) AS can_delete"
        args = (viewer_id,)
    if not include_all:
        args += (owner_id,)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT " + fields + " FROM records"
            + ("" if include_all else " WHERE owner_id = ?")
            + " ORDER BY id DESC LIMIT 100",
            args,
        ).fetchall()
    records = [dict(row) for row in rows]
    if viewer_id is not None:
        for record in records:
            record["can_delete"] = bool(record["can_delete"])
    return records


def get_record(record_id: int, *, owner_id: int | None = None, include_all: bool = True) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, title, text, result, created_at, updated_at,"
            " source_input, source_image, source_transcript FROM records"
            " WHERE id = ?" + ("" if include_all else " AND owner_id = ?"),
            (record_id,) if include_all else (record_id, owner_id),
        ).fetchone()
    if row is None:
        return None
    record = dict(row)
    try:
        result = json.loads(record["result"])
    except (json.JSONDecodeError, TypeError) as exc:
        raise RecordDataError(f"记录 {record_id} 的结果无法解析") from exc
    if not isinstance(result, dict):
        raise RecordDataError(f"记录 {record_id} 的结果不是 JSON 对象")
    result.pop('customer_profile', None)
    record["result"] = result
    if record["source_input"] is not None:
        try:
            record["source_input"] = json.loads(record["source_input"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise RecordDataError(f"记录 {record_id} 的原始输入无法解析") from exc
        if not isinstance(record["source_input"], dict):
            raise RecordDataError(f"记录 {record_id} 的原始输入不是 JSON 对象")
    return record


def update_result(record_id: int, result: dict, *, owner_id: int | None = None, include_all: bool = True) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT result FROM records WHERE id=?" + ("" if include_all else " AND owner_id=?"),
                                (record_id,) if include_all else (record_id, owner_id)).fetchone()
        if existing is None:
            return False
        from record_actions import preserve_action_states
        result = preserve_action_states(json.loads(existing["result"]), result)
        result.pop("customer_profile", None)
        cur = conn.execute(
            "UPDATE records SET result = ?, updated_at = ? WHERE id = ?"
            + ("" if include_all else " AND owner_id = ?"),
            (json.dumps(result, ensure_ascii=False), now, record_id)
            + (() if include_all else (owner_id,)),
        )
        if cur.rowcount:
            row = conn.execute("SELECT owner_id FROM records WHERE id=?", (record_id,)).fetchone()
            if row is not None:
                from calendar_store import sync_record_tasks
                sync_record_tasks(conn, row["owner_id"], record_id, result)
        return cur.rowcount > 0
