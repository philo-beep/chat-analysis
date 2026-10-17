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
    try:
        with conn:
            yield conn
    finally:
        # sqlite3.Connection 自身的上下文管理器只提交/回滚，不会关闭连接。
        conn.close()


def init_db() -> None:
    with _connect() as conn:
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
        }.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE records ADD COLUMN {name} {declaration}")


def save_record(
    text: str, result: dict, *, source_input: dict | None = None,
    source_image: str | None = None, source_transcript: str = "",
) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    title = text.strip().splitlines()[0][:30] if text.strip() else "未命名"
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO records (title, text, result, created_at, updated_at,"
            " source_input, source_image, source_transcript) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, text, json.dumps(result, ensure_ascii=False), now, now,
             json.dumps(source_input, ensure_ascii=False) if source_input is not None else None,
             source_image, source_transcript),
        )
        return int(cur.lastrowid)


def list_records() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM records"
            " ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [dict(row) for row in rows]


def get_record(record_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, title, text, result, created_at, updated_at,"
            " source_input, source_image, source_transcript FROM records"
            " WHERE id = ?",
            (record_id,),
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
    record["result"] = result
    if record["source_input"] is not None:
        try:
            record["source_input"] = json.loads(record["source_input"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise RecordDataError(f"记录 {record_id} 的原始输入无法解析") from exc
        if not isinstance(record["source_input"], dict):
            raise RecordDataError(f"记录 {record_id} 的原始输入不是 JSON 对象")
    return record


def update_result(record_id: int, result: dict) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE records SET result = ?, updated_at = ? WHERE id = ?",
            (json.dumps(result, ensure_ascii=False), now, record_id),
        )
        return cur.rowcount > 0
