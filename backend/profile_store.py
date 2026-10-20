"""Owner-scoped customer profiles, historical evidence, and optimistic updates."""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone


FIELDS = ("display_name", "role", "company", "industry", "concerns", "decision_style",
          "communication_preferences", "risk_points", "next_follow_up",
          "communication_strategy", "communication_points")
LIST_FIELDS = {"concerns", "communication_preferences", "risk_points", "communication_points"}


class ProfileError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(message)


class ProfileConflictError(ProfileError):
    def __init__(self):
        super().__init__(409, "这位客户的资料刚有更新，请重新整理本次聊天。")


def init_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS customer_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        identity_key TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '未知', role TEXT NOT NULL DEFAULT '未知',
        company TEXT NOT NULL DEFAULT '未知', industry TEXT NOT NULL DEFAULT '未知',
        concerns_json TEXT NOT NULL DEFAULT '[]', decision_style TEXT NOT NULL DEFAULT '未知',
        communication_preferences_json TEXT NOT NULL DEFAULT '[]',
        risk_points_json TEXT NOT NULL DEFAULT '[]', next_follow_up TEXT NOT NULL DEFAULT '未知',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(owner_id, identity_key))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS customer_profile_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES customer_profiles(id) ON DELETE CASCADE,
        source_record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
        snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(profile_id, source_record_id))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_snapshots_record ON customer_profile_snapshots(source_record_id)")
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(customer_profiles)")}
    for name, declaration in {
        "communication_strategy": "TEXT NOT NULL DEFAULT ''",
        "communication_points_json": "TEXT NOT NULL DEFAULT '[]'",
        "version": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE customer_profiles ADD COLUMN {name} {declaration}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_owner_updated ON customer_profiles(owner_id,updated_at DESC,id DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_snapshots_timeline ON customer_profile_snapshots(profile_id,created_at DESC,id DESC)")


def _timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _normalize(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def _identity(profile, record_id):
    name = _normalize(profile.get("display_name", "未知"))
    company = _normalize(profile.get("company", "未知"))
    unknown = {"", "未知", "不详", "不确定", "unknown", "客户", "甲方", "对方"}
    # A title such as 王总 is insufficient evidence that two chats concern one person.
    abbreviated = bool(re.fullmatch(r".{1,2}(?:总|经理|老板|先生|女士)", name))
    if name in unknown or company in unknown or abbreviated:
        return f"temporary:record:{record_id}"
    return "named:" + hashlib.sha256((name + "\0" + company).encode()).hexdigest()


def _profile_values(profile):
    return {name: profile.get(name, [] if name in LIST_FIELDS else "" if name == "communication_strategy" else "未知")
            for name in FIELDS}


def _serialize(row):
    item = dict(row)
    for name in LIST_FIELDS:
        item[name] = json.loads(item.pop(name + "_json", "[]"))
    item.pop("owner_id", None)
    item.pop("identity_key", None)
    return item


def context_for_identity(owner_id, identity):
    """Only exact full-name/company matches can supply trusted prior facts.

    Pass the whole return value to save_snapshot(profile_context=...) after the
    model call. The profile subobject alone is suitable for model context.
    """
    import database
    key = _identity(identity, 0)
    if key.startswith("temporary:"):
        return {"profile_id": None, "version": 0, "identity_key": None, "profile": None}
    with database._connect() as conn:
        row = conn.execute("SELECT * FROM customer_profiles WHERE owner_id=? AND identity_key=?",
                           (owner_id, key)).fetchone()
    return {"profile_id": row["id"] if row else None, "version": row["version"] if row else 0,
            "identity_key": key, "profile": _profile_values(_serialize(row)) if row else None}


def has_named_profiles(owner_id):
    """Only identifiable profiles can contribute context to a later chat."""
    import database
    with database._connect() as conn:
        return conn.execute("SELECT 1 FROM customer_profiles WHERE owner_id=? AND identity_key LIKE 'named:%' LIMIT 1",
                            (owner_id,)).fetchone() is not None


lookup_profile = context_for_identity


def list_customers(owner_id, *, q="", limit=50, offset=0):
    import database
    args = [owner_id]
    where = "p.owner_id=?"
    if q.strip():
        value = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where += " AND (p.display_name LIKE ? ESCAPE '\\' OR p.company LIKE ? ESCAPE '\\')"
        args.extend(["%" + value + "%"] * 2)
    with database._connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM customer_profiles p WHERE " + where, args).fetchone()[0]
        rows = conn.execute("SELECT p.*, (SELECT COUNT(*) FROM customer_profile_snapshots s WHERE s.profile_id=p.id) "
                            "AS snapshot_count FROM customer_profiles p WHERE " + where
                            + " ORDER BY p.updated_at DESC,p.id DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
    items = [_serialize(row) for row in rows]
    for item in items:
        item["last_analyzed_at"] = item["updated_at"]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_customer(owner_id, profile_id):
    import database
    with database._connect() as conn:
        row = conn.execute("SELECT p.*, (SELECT COUNT(*) FROM customer_profile_snapshots s WHERE s.profile_id=p.id) "
                           "AS snapshot_count FROM customer_profiles p WHERE p.id=? AND p.owner_id=?",
                           (profile_id, owner_id)).fetchone()
    if row is None:
        raise ProfileError(404, "没有找到这位客户。")
    item = _serialize(row)
    item["last_analyzed_at"] = item["updated_at"]
    return {"id": item["id"], "profile": _profile_values(item), "version": item["version"],
            "created_at": item["created_at"], "updated_at": item["updated_at"],
            "last_analyzed_at": item["last_analyzed_at"], "snapshot_count": item["snapshot_count"]}


def list_snapshots(owner_id, profile_id, *, limit=50, offset=0):
    import database
    with database._connect() as conn:
        if conn.execute("SELECT 1 FROM customer_profiles WHERE id=? AND owner_id=?", (profile_id, owner_id)).fetchone() is None:
            raise ProfileError(404, "没有找到这位客户。")
        total = conn.execute("SELECT COUNT(*) FROM customer_profile_snapshots WHERE profile_id=?", (profile_id,)).fetchone()[0]
        rows = conn.execute("SELECT s.id,s.profile_id,s.source_record_id,s.created_at FROM customer_profile_snapshots s "
                            "JOIN customer_profiles p ON p.id=s.profile_id WHERE p.owner_id=? AND p.id=? "
                            "ORDER BY s.created_at DESC,s.id DESC LIMIT ? OFFSET ?",
                            (owner_id, profile_id, limit, offset)).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def get_snapshot(owner_id, profile_id, snapshot_id):
    import database
    with database._connect() as conn:
        row = conn.execute("SELECT s.* FROM customer_profile_snapshots s JOIN customer_profiles p ON p.id=s.profile_id "
                           "WHERE s.id=? AND s.profile_id=? AND p.owner_id=?", (snapshot_id, profile_id, owner_id)).fetchone()
    if row is None:
        raise ProfileError(404, "没有找到这份历史资料。")
    item = {key: row[key] for key in ("id", "profile_id", "source_record_id", "created_at")}
    item["profile"] = _profile_values(json.loads(row["snapshot_json"]))
    return item


def _write_current(conn, profile_id, profile, timestamp):
    profile = _profile_values(profile)
    columns = [name + "_json" if name in LIST_FIELDS else name for name in FIELDS]
    values = [json.dumps(profile.get(name, []), ensure_ascii=False) if name in LIST_FIELDS
              else profile.get(name, "未知") for name in FIELDS]
    conn.execute("UPDATE customer_profiles SET " + ",".join(name + "=?" for name in columns)
                 + ",updated_at=?,version=version+1 WHERE id=?", (*values, timestamp, profile_id))


def _refresh_or_delete(conn, profile_id):
    latest = conn.execute("SELECT snapshot_json,created_at FROM customer_profile_snapshots "
                          "WHERE profile_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (profile_id,)).fetchone()
    if latest is None:
        conn.execute("DELETE FROM customer_profiles WHERE id=?", (profile_id,))
    else:
        _write_current(conn, profile_id, json.loads(latest["snapshot_json"]), latest["created_at"])


def save_snapshot(conn, owner_id, record_id, profile, *, profile_context=None, expected_context=None):
    """Called inside the same transaction as the originating record write."""
    if owner_id is None or profile is None:
        return
    if profile_context is None:
        profile_context = expected_context
    timestamp = _timestamp()
    identity = _identity(profile, record_id)
    target_id = profile_context.get("profile_id") if profile_context else None
    if target_id is not None:
        current = conn.execute("SELECT id,version,identity_key FROM customer_profiles WHERE id=? AND owner_id=?",
                               (target_id, owner_id)).fetchone()
        if current is None or current["version"] != profile_context.get("version"):
            raise ProfileConflictError()
        # An explicit correction to the customer's company/name must retain its
        # history, but may not absorb another existing customer's history.
        if identity.startswith("named:") and identity != current["identity_key"]:
            duplicate = conn.execute("SELECT 1 FROM customer_profiles WHERE owner_id=? AND identity_key=? AND id<>?",
                                     (owner_id, identity, target_id)).fetchone()
            if duplicate:
                raise ProfileConflictError()
            conn.execute("UPDATE customer_profiles SET identity_key=? WHERE id=?", (identity, target_id))
        profile_id = target_id
    else:
        expected_key = profile_context.get("identity_key") if profile_context else None
        if expected_key is not None:
            if identity != expected_key or conn.execute("SELECT 1 FROM customer_profiles WHERE owner_id=? AND identity_key=?",
                                                       (owner_id, identity)).fetchone():
                raise ProfileConflictError()
        conn.execute("INSERT OR IGNORE INTO customer_profiles(owner_id,identity_key,created_at,updated_at) VALUES(?,?,?,?)",
                     (owner_id, identity, timestamp, timestamp))
        profile_id = conn.execute("SELECT id FROM customer_profiles WHERE owner_id=? AND identity_key=?",
                                  (owner_id, identity)).fetchone()[0]
    profile = _profile_values(profile)
    old_ids = [row[0] for row in conn.execute("SELECT profile_id FROM customer_profile_snapshots WHERE source_record_id=? AND profile_id<>?",
                                             (record_id, profile_id))]
    conn.execute("DELETE FROM customer_profile_snapshots WHERE source_record_id=? AND profile_id<>?", (record_id, profile_id))
    conn.execute("INSERT INTO customer_profile_snapshots(profile_id,source_record_id,snapshot_json,created_at) VALUES(?,?,?,?) "
                 "ON CONFLICT(profile_id,source_record_id) DO UPDATE SET snapshot_json=excluded.snapshot_json,created_at=excluded.created_at",
                 (profile_id, record_id, json.dumps(profile, ensure_ascii=False), timestamp))
    _write_current(conn, profile_id, profile, timestamp)
    for old_id in old_ids:
        _refresh_or_delete(conn, old_id)


def delete_record_snapshots(conn, record_id):
    """Remove source-derived facts and restore the latest remaining evidence."""
    profile_ids = [row[0] for row in conn.execute("SELECT profile_id FROM customer_profile_snapshots WHERE source_record_id=?", (record_id,))]
    conn.execute("DELETE FROM customer_profile_snapshots WHERE source_record_id=?", (record_id,))
    for profile_id in profile_ids:
        _refresh_or_delete(conn, profile_id)
