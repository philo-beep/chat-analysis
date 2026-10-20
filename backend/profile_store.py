"""Private customer profiles and per-chat snapshots; never serialized with records."""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone


FIELDS = ("display_name", "role", "company", "industry", "concerns", "decision_style",
          "communication_preferences", "risk_points", "next_follow_up")
LIST_FIELDS = {"concerns", "communication_preferences", "risk_points"}


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


def _write_current(conn, profile_id, profile, timestamp):
    columns = [name + "_json" if name in LIST_FIELDS else name for name in FIELDS]
    values = [json.dumps(profile.get(name, []), ensure_ascii=False) if name in LIST_FIELDS
              else profile.get(name, "未知") for name in FIELDS]
    conn.execute("UPDATE customer_profiles SET " + ",".join(name + "=?" for name in columns)
                 + ",updated_at=? WHERE id=?", (*values, timestamp, profile_id))


def _refresh_or_delete(conn, profile_id):
    latest = conn.execute("SELECT snapshot_json,created_at FROM customer_profile_snapshots "
                          "WHERE profile_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (profile_id,)).fetchone()
    if latest is None:
        conn.execute("DELETE FROM customer_profiles WHERE id=?", (profile_id,))
    else:
        _write_current(conn, profile_id, json.loads(latest["snapshot_json"]), latest["created_at"])


def save_snapshot(conn, owner_id, record_id, profile):
    """Called inside the same transaction as the originating record write."""
    if owner_id is None or profile is None:
        return
    timestamp = _timestamp()
    identity = _identity(profile, record_id)
    conn.execute("INSERT OR IGNORE INTO customer_profiles(owner_id,identity_key,created_at,updated_at) VALUES(?,?,?,?)",
                 (owner_id, identity, timestamp, timestamp))
    profile_id = conn.execute("SELECT id FROM customer_profiles WHERE owner_id=? AND identity_key=?",
                              (owner_id, identity)).fetchone()[0]
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
