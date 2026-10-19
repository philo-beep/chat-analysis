"""Owner-scoped scheduled and unscheduled tasks, stored in the existing SQLite DB."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import database

BUSINESS_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")
TIMEZONE = "Asia/Shanghai"


class CalendarError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


def now() -> datetime:
    return datetime.now(BUSINESS_TZ)


def today() -> date:
    return now().date()


def init_schema(conn) -> None:
    # The caller owns the migration transaction; no executescript implicit commits.
    conn.execute("""CREATE TABLE IF NOT EXISTS task_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 200),
        notes TEXT NOT NULL DEFAULT '' CHECK(length(notes)<=5000),
        due_date TEXT, start_date TEXT,
        manual_level INTEGER CHECK(manual_level BETWEEN 1 AND 5),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT,
        source_record_id INTEGER REFERENCES records(id) ON DELETE SET NULL,
        source_task_key TEXT,
        UNIQUE(owner_id, source_task_key))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_items_schedule ON task_items(owner_id, completed_at, due_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_items_source ON task_items(source_record_id)")


def serialize(row, reference: date | None = None) -> dict:
    item = dict(row)
    reference = reference or today()
    start = item["start_date"] or datetime.fromisoformat(item["created_at"]).astimezone(BUSINESS_TZ).date().isoformat()
    due = date.fromisoformat(item["due_date"]) if item["due_date"] else None
    remaining = (due - reference).days if due else None
    auto_level = (5 if remaining <= 2 else 4 if remaining <= 4 else 3 if remaining <= 6 else 2 if remaining <= 8 else 1) if due else None
    item.update(effective_start_date=start, is_manual=item["manual_level"] is not None,
                completed=item["completed_at"] is not None,
                urgency_level=item["manual_level"] if item["manual_level"] is not None else auto_level,
                is_overdue=bool(due and due < reference and not item["completed_at"]),
                date_anomaly=bool(due and due.isoformat() < start))
    # Ownership is enforced in SQL; do not expose another internal user identifier.
    item.pop("owner_id", None)
    return item


def _get(conn, owner_id: int, item_id: int):
    row = conn.execute("SELECT * FROM task_items WHERE id=? AND owner_id=?", (item_id, owner_id)).fetchone()
    if row is None:
        raise CalendarError(404, "事项不存在")
    return row


def get_item(owner_id: int, item_id: int) -> dict:
    with database._connect() as conn:
        return serialize(_get(conn, owner_id, item_id))


def _insert(conn, owner_id, values, *, source_record_id=None, source_task_key=None):
    timestamp = now().isoformat(timespec="seconds")
    cursor = conn.execute("""INSERT INTO task_items
        (owner_id,title,notes,due_date,manual_level,created_at,updated_at,source_record_id,source_task_key)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (owner_id, values["title"], values.get("notes", ""), values.get("due_date"),
         values.get("manual_level"), timestamp, timestamp, source_record_id, source_task_key))
    return serialize(_get(conn, owner_id, cursor.lastrowid))


def create_item(owner_id: int, values: dict) -> dict:
    with database._connect() as conn:
        return _insert(conn, owner_id, values)


def update_item(owner_id: int, item_id: int, values: dict) -> dict:
    allowed = {"title", "notes", "due_date", "manual_level"}
    if not values or not set(values) <= allowed:
        raise CalendarError(422, "请提供需要修改的事项字段")
    with database._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _get(conn, owner_id, item_id)
        changes = dict(values, updated_at=now().isoformat(timespec="seconds"))
        conn.execute("UPDATE task_items SET " + ",".join(f"{key}=?" for key in changes) + " WHERE id=? AND owner_id=?",
                     (*changes.values(), item_id, owner_id))
        return serialize(_get(conn, owner_id, item_id))


def complete_item(owner_id: int, item_id: int, completed: bool) -> dict:
    with database._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get(conn, owner_id, item_id)
        timestamp = now().isoformat(timespec="seconds")
        # Repeated completion does not move the actual end timestamp.
        completed_at = (row["completed_at"] or timestamp) if completed else None
        conn.execute("UPDATE task_items SET completed_at=?,updated_at=? WHERE id=? AND owner_id=?",
                     (completed_at, timestamp, item_id, owner_id))
        return serialize(_get(conn, owner_id, item_id))


def delete_item(owner_id: int, item_id: int) -> dict:
    with database._connect() as conn:
        cursor = conn.execute("DELETE FROM task_items WHERE id=? AND owner_id=?", (item_id, owner_id))
        if not cursor.rowcount:
            raise CalendarError(404, "事项不存在")
    return {"id": item_id, "deleted": True}


def list_items(owner_id: int, *, from_date=None, to_date=None, scheduled=None,
               status="open", limit=500, offset=0) -> dict:
    reference = today()
    filters, args = ["owner_id=?"], [owner_id]
    if status != "all":
        filters.append("completed_at IS " + ("NOT NULL" if status == "completed" else "NULL"))
    if scheduled is not None:
        filters.append("due_date IS " + ("NOT NULL" if scheduled else "NULL"))
    if from_date or to_date:
        filters.append("due_date IS NOT NULL")
        # An invalid reverse range is shown at its DDL as an explicit anomaly.
        start = "COALESCE(start_date,substr(created_at,1,10))"
        if to_date:
            filters.append(f"min({start},due_date)<=?")
            args.append(to_date)
        if from_date:
            # Overdue open tasks remain visible today and in the Gantt overtime segment.
            filters.append("(CASE WHEN completed_at IS NULL AND due_date<? THEN ? ELSE due_date END)>=?")
            args.extend([reference.isoformat(), reference.isoformat(), from_date])
    where = " AND ".join(filters)
    with database._connect() as conn:
        conn.execute("BEGIN")
        total = conn.execute("SELECT COUNT(*) FROM task_items WHERE " + where, args).fetchone()[0]
        rows = conn.execute("SELECT * FROM task_items WHERE " + where +
                            " ORDER BY (due_date IS NULL),due_date,id DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
    return {"items": [serialize(row, reference) for row in rows], "total": total,
            "today": reference.isoformat(), "timezone": TIMEZONE}


def import_record_task(user: dict, record_id: int, task_index: int, expected_text: str) -> dict:
    with database._connect() as conn:
        # Check the snapshot and insert in the same transaction; updates cannot race import.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT result FROM records WHERE id=?" +
                           ("" if "records:all" in user["permissions"] else " AND owner_id=?"),
                           (record_id,) if "records:all" in user["permissions"] else (record_id, user["id"])).fetchone()
        if row is None:
            raise CalendarError(404, "来源聊天不存在")
        try:
            result = json.loads(row["result"])
            tasks = result.get("tasks") if isinstance(result, dict) else None
        except (json.JSONDecodeError, TypeError):
            raise CalendarError(409, "来源聊天数据无法读取") from None
        if not isinstance(tasks, list) or task_index >= len(tasks) or tasks[task_index] != expected_text:
            raise CalendarError(409, "来源建议已更新，请刷新后重新加入待办池")
        # Keep the entire original suggestion in notes if it exceeds the title limit.
        title = expected_text.strip()
        if not title:
            raise CalendarError(422, "不能导入空白建议")
        key = f"{record_id}:{task_index}:" + hashlib.sha256(expected_text.encode("utf-8")).hexdigest()
        existing = conn.execute("SELECT * FROM task_items WHERE owner_id=? AND source_task_key=?", (user["id"], key)).fetchone()
        if existing:
            return serialize(existing)
        if len(title) > 5000:
            raise CalendarError(422, "建议超过 5000 字，无法完整保存；请先精简来源建议")
        return _insert(conn, user["id"], {"title": title[:200], "notes": title if len(title) > 200 else ""},
                       source_record_id=record_id, source_task_key=key)
