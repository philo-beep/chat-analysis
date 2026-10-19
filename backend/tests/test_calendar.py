"""Calendar HTTP regressions against isolated SQLite; never touch app.db."""

import json
import os
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import auth_store
import calendar_store as store
import database
import main

PASSWORD = "Calendar-test-password-739!"
FIXED_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=store.BUSINESS_TZ)


class CalendarTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(database, "DB_PATH", Path(directory) / "calendar.db"))
        self.enterContext(patch.dict(os.environ, {"KEYOUSHU_JWT_SECRET": "calendar-isolated-test-key-at-least-32-characters"}))
        self.enterContext(patch.object(store, "now", return_value=FIXED_NOW))
        self.client = self.enterContext(TestClient(main.app, raise_server_exceptions=False))
        self.owner = auth_store.create_user("calendar_owner", PASSWORD)
        self.other = auth_store.create_user("calendar_other", PASSWORD, ["admin"])
        self.viewer = auth_store.create_user("calendar_viewer", PASSWORD, ["viewer"])
        self.headers = self.login("calendar_owner")
        self.other_headers = self.login("calendar_other")
        self.viewer_headers = self.login("calendar_viewer")

    def login(self, username):
        response = self.client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": "Bearer " + response.json()["data"]["token"]}

    def request(self, method, path="", *, payload=None, headers=None, status=200):
        kwargs = {"headers": self.headers if headers is None else headers}
        if payload is not None:
            kwargs["json"] = payload
        response = getattr(self.client, method)("/api/calendar/items" + path, **kwargs)
        self.assertEqual(response.status_code, status, response.text)
        body = response.json()
        self.assertEqual(set(body), {"code", "message", "data"})
        return body["data"]

    def create(self, **fields):
        return self.request("post", payload={"title": "准备方案", **fields})

    def test_task_pool_schedule_manual_restore_complete_reopen_delete(self):
        item = self.create(title="  准备方案  ")
        self.assertEqual(item["title"], "准备方案")
        self.assertIsNone(item["start_date"])
        self.assertEqual(item["effective_start_date"], "2026-10-19")
        self.assertTrue(item["created_at"].endswith("+08:00"))
        pool = self.request("get", "?scheduled=false")
        self.assertEqual(pool["total"], 1)
        self.assertEqual(pool["timezone"], "Asia/Shanghai")
        identifier = f"/{item['id']}"
        item = self.request("patch", identifier, payload={"due_date": "2026-10-22"})
        self.assertEqual(item["urgency_level"], 4)
        self.assertEqual(self.request("get", "?scheduled=false")["total"], 0)
        item = self.request("patch", identifier, payload={"manual_level": 5})
        self.assertEqual((item["is_manual"], item["urgency_level"]), (True, 5))
        with patch.object(store, "today", return_value=date(2026, 10, 1)):
            self.assertEqual(self.request("get", identifier)["urgency_level"], 5)
        item = self.request("patch", identifier, payload={"manual_level": None})
        self.assertEqual((item["is_manual"], item["urgency_level"]), (False, 4))
        item = self.request("patch", identifier, payload={"due_date": "2026-10-18"})
        self.assertTrue(item["is_overdue"])
        self.assertTrue(item["date_anomaly"])
        done = self.request("patch", identifier + "/completion", payload={"completed": True})
        self.assertTrue(done["completed"])
        self.assertFalse(done["is_overdue"])
        self.assertEqual(self.request("get")["total"], 0)
        self.assertEqual(self.request("get", "?status=completed")["total"], 1)
        later = datetime(2026, 10, 20, 1, 0, tzinfo=store.BUSINESS_TZ)
        with patch.object(store, "now", return_value=later):
            repeat = self.request("patch", identifier + "/completion", payload={"completed": True})
            self.assertEqual(repeat["completed_at"], done["completed_at"])
        reopened = self.request("patch", identifier + "/completion", payload={"completed": False})
        self.assertIsNone(reopened["completed_at"])
        self.assertEqual(self.request("get")["total"], 1)
        self.assertEqual(self.request("delete", identifier), {"id": item["id"], "deleted": True})
        self.request("get", identifier, status=404)

    def test_automatic_levels_and_timezone_date_boundary(self):
        item = self.create(due_date="2026-10-22")
        row = dict(item, owner_id=self.owner["id"])
        for remaining, expected in [(-1, 5), (0, 5), (2, 5), (3, 4), (4, 4), (5, 3), (6, 3), (7, 2), (8, 2), (9, 1), (99, 1)]:
            with self.subTest(remaining=remaining):
                from datetime import timedelta
                row["due_date"] = (date(2026, 10, 19) + timedelta(days=remaining)).isoformat()
                self.assertEqual(store.serialize(row)["urgency_level"], expected)
        row.update(created_at="2026-10-18T18:00:00+00:00", start_date=None)
        self.assertEqual(store.serialize(row)["effective_start_date"], "2026-10-19")
        row["start_date"] = "2026-10-10"
        self.assertEqual(store.serialize(row)["effective_start_date"], "2026-10-10")

    def test_owner_isolation_even_for_admin_and_permission_errors(self):
        item = self.create(due_date="2026-10-22")
        identifier = f"/{item['id']}"
        self.assertEqual(self.request("get", headers=self.other_headers)["total"], 0)
        for method, path, payload in [("get", identifier, None), ("patch", identifier, {"title": "偷改"}),
                                      ("delete", identifier, None),
                                      ("patch", identifier + "/completion", {"completed": True})]:
            self.request(method, path, payload=payload, headers=self.other_headers, status=404)
        self.request("get", headers={}, status=401)
        self.request("get", headers={"Authorization": "Bearer invalid"}, status=401)
        self.request("post", payload={"title": "禁止写"}, headers=self.viewer_headers, status=403)
        self.assertEqual(self.request("get", headers=self.viewer_headers)["total"], 0)
        self.assertEqual(self.request("get", identifier)["title"], "准备方案")

    def test_reject_malformed_input_and_backend_managed_fields(self):
        item = self.create()
        invalid_creates = [{"title": " "}, {"title": None}, {"title": "x", "notes": None},
                           {"title": "x", "due_date": "2026-02-30"}, {"title": "x", "due_date": "20261022"},
                           {"title": "x", "manual_level": 6}, {"title": "x", "manual_level": True},
                           {"title": "x", "start_date": "2026-01-01"}, {"title": "x", "owner_id": self.other["id"]},
                           {"title": "x", "created_at": "2026-01-01"}, {"title": "x" * 201}]
        for payload in invalid_creates:
            with self.subTest(payload=payload):
                self.request("post", payload=payload, status=422)
        for payload in [{}, {"title": None}, {"notes": None}, {"start_date": "2026-01-01"}, {"completed": True}]:
            self.request("patch", f"/{item['id']}", payload=payload, status=422)
        self.request("patch", f"/{item['id']}/completion", payload={"completed": "true"}, status=422)
        self.assertEqual(self.request("get")["total"], 1)

    def test_inclusive_overlap_overdue_extension_and_pagination(self):
        first = self.create(title="跨月", due_date="2026-11-05")
        second = self.create(title="逾期", due_date="2026-10-15")
        self.create(title="无日期")
        with database._connect() as conn:
            conn.execute("UPDATE task_items SET start_date='2026-09-29' WHERE id IN (?,?)", (first["id"], second["id"]))
        for query in ["?from=2026-09-29&to=2026-09-29", "?from=2026-10-19&to=2026-10-19"]:
            self.assertEqual(self.request("get", query)["total"], 2)
        self.assertEqual(self.request("get", "?from=2026-11-05&to=2026-11-05")["total"], 1)
        self.assertEqual(self.request("get", "?from=2026-11-06&to=2026-11-06")["total"], 0)
        page = self.request("get", "?limit=1&offset=1")
        self.assertEqual((len(page["items"]), page["total"]), (1, 3))
        for query in ["?from=2026-10-20&to=2026-10-01", "?from=bad", "?limit=501", "?offset=-1",
                      "?scheduled=false&from=2026-10-01", "?status=invalid"]:
            self.request("get", query, status=422)

    def test_earlier_deadline_anomaly_is_queryable_at_due_date(self):
        item = self.create(due_date="2026-10-18")
        self.assertTrue(item["date_anomaly"])
        items = self.request("get", "?from=2026-10-18&to=2026-10-18")["items"]
        self.assertEqual([record["id"] for record in items], [item["id"]])

    def test_record_import_snapshot_idempotency_and_no_cross_owner(self):
        record_id = database.save_record("测试聊天", {"tasks": ["确认方案", "发报价"]}, owner_id=self.owner["id"])
        payload = {"record_id": record_id, "task_index": 0, "expected_text": "确认方案"}
        item = self.request("post", "/from-record", payload=payload)
        again = self.request("post", "/from-record", payload=payload)
        self.assertEqual(item["id"], again["id"])
        self.assertEqual(item["source_record_id"], record_id)
        self.assertIsNone(item["due_date"])
        self.assertIsNone(item["start_date"])
        self.request("post", "/from-record", payload=payload, headers=self.viewer_headers, status=403)
        member = auth_store.create_user("another_member", PASSWORD)
        self.request("post", "/from-record", payload=payload, headers=self.login(member["username"]), status=404)
        # records:all admins can import an accessible source into their own pool only.
        admin_item = self.request("post", "/from-record", payload=payload, headers=self.other_headers)
        self.assertNotEqual(item["id"], admin_item["id"])
        database.update_result(record_id, {"tasks": ["更新后的任务"]})
        self.request("post", "/from-record", payload=payload, status=409)
        self.assertEqual(self.request("get")["total"], 1)
        self.request("post", "/from-record", payload={**payload, "task_index": 99}, status=409)

    def test_source_corruption_does_not_insert_partial_task(self):
        record_id = database.save_record("损坏来源", {"tasks": []}, owner_id=self.owner["id"])
        with database._connect() as conn:
            conn.execute("UPDATE records SET result='not-json' WHERE id=?", (record_id,))
        self.request("post", "/from-record", payload={"record_id": record_id, "task_index": 0, "expected_text": "任务"}, status=409)
        self.assertEqual(self.request("get")["total"], 0)

    def test_idempotent_migration_preserves_records_and_tasks(self):
        record_id = database.save_record("旧记录", {"tasks": ["旧任务"]}, owner_id=self.owner["id"])
        item = self.create()
        database.init_db()
        database.init_db()
        self.assertEqual(database.get_record(record_id)["result"]["tasks"], ["旧任务"])
        self.assertEqual(self.request("get", f"/{item['id']}")["title"], "准备方案")
        # Upgrade a database whose records table predates access control/source fields.
        legacy_path = database.DB_PATH.parent / "legacy.db"
        with closing(sqlite3.connect(legacy_path)) as conn:
            with conn:
                conn.execute("CREATE TABLE records(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,text TEXT NOT NULL,result TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)")
                conn.execute("INSERT INTO records(title,text,result,created_at,updated_at) VALUES(?,?,?,?,?)",
                             ("旧", "旧", json.dumps({"tasks": []}), "2026-01-01T12:00:00", "2026-01-01T12:00:00"))
        with patch.object(database, "DB_PATH", legacy_path):
            database.init_db()
            database.init_db()
            with database._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM task_items").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
