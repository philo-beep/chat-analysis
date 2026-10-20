"""Isolated transactions for private profiles, explicit decisions and legacy behavior."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auth_store
import calendar_store
import database
import profile_store
import record_actions


def expanded():
    return {"requirements": [], "questions": [{"question": "日期对吗？", "initial_guess": "周五", "related_ddl_index": 0}],
            "tasks": ["核对库存"], "reply": "收到", "analysis_version": 2,
            "ddl_tasks": [{"title": "发样品", "ddl_date": "2026-10-30", "start_date": "2026-10-21",
                           "source_quote": "下周五发样品", "date_basis": "inferred"}],
            "suggested_tasks": [{"title": "准备对比表", "reason": "客户提到竞品", "priority": "high"}]}


def profile(name="张三", company="演示采购公司", concern="交期"):
    return {"display_name": name, "role": "采购", "company": company, "industry": "服装",
            "concerns": [concern], "decision_style": "需内部确认", "communication_preferences": [],
            "risk_points": [], "next_follow_up": "提交方案"}


class ExpandedPersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]))
        self.enterContext(patch.object(database, "DB_PATH", Path(directory) / "test.db"))
        database.init_db()
        self.user = auth_store.create_user("expanded_owner", "Test-password-987!")
        self.other = auth_store.create_user("expanded_other", "Test-password-987!")

    def save(self, output=None, customer=None, owner=None):
        result = output if output is not None else expanded()
        return database.save_record("客户：下周五发样品", result, owner_id=(owner or self.user)["id"], customer_profile=customer)

    def action(self, rid, action, index=0, source=None, title=None, **kwargs):
        result = database.get_record(rid)["result"]
        field = "ddl_tasks" if action == "add_ddl_task" else "questions" if action == "confirm_question" else source
        item = result[field][index]
        title = title or (item if isinstance(item, str) else item.get("question", item.get("title")))
        return record_actions.apply_action(self.user, rid, {"action": action, "index": index,
            "expected_result": result, **({"kind": source} if source else {}), **kwargs})

    def test_new_record_no_automatic_tasks_and_actions_are_idempotent(self):
        rid = self.save()
        self.assertEqual(calendar_store.list_items(self.user["id"])["total"], 0)
        first = self.action(rid, "add_ddl_task")
        self.assertEqual(first["item"]["start_date"], "2026-10-21")
        self.assertEqual(first["item"]["due_date"], "2026-10-30")
        self.assertEqual(self.action(rid, "add_ddl_task")["item"]["id"], first["item"]["id"])
        for source in ("tasks", "suggested_tasks"):
            accepted = self.action(rid, "accept_suggestion", source=source)
            self.assertIsNone(accepted["item"]["due_date"])
            self.assertEqual(self.action(rid, "accept_suggestion", source=source)["item"]["id"], accepted["item"]["id"])
        self.assertEqual(calendar_store.list_items(self.user["id"])["total"], 3)
        answer = self.action(rid, "confirm_question", answer="改为周四")
        self.assertEqual(answer["record"]["result"]["questions"][0]["confirmed_answer"], "改为周四")

    def test_legacy_sync_preserved_and_legacy_import_deduplicated(self):
        old = {k: v for k, v in expanded().items() if k in {"requirements", "tasks", "reply"}}
        old["questions"] = []
        rid = self.save(old)
        self.assertEqual(calendar_store.list_items(self.user["id"])["total"], 1)
        accepted = self.action(rid, "accept_suggestion", source="tasks")
        self.assertEqual(calendar_store.list_items(self.user["id"])["total"], 1)
        self.assertEqual(accepted["record"]["result"]["action_states"]["0"]["status"], "accepted")

    def test_ignored_suggestion_creates_no_task_and_ownership_conflict_checks(self):
        rid = self.save()
        self.assertEqual(self.action(rid, "ignore_suggestion", source="suggested_tasks")["record"]["result"]["suggested_tasks"][0]["status"], "ignored")
        self.assertEqual(calendar_store.list_items(self.user["id"])["total"], 0)
        for actor, title, status in ((self.other, "发样品", 404), (self.user, "被修改的标题", 409)):
            with self.assertRaises(calendar_store.CalendarError) as error:
                record_actions.apply_action(actor, rid, {"action": "add_ddl_task", "index": 0, "expected_title": title})
            self.assertEqual(error.exception.status, status)

    def test_profile_not_returned_merges_per_owner_and_retains_snapshots(self):
        value = expanded()
        value["customer_profile"] = profile()
        first = self.save(value)
        self.assertNotIn("customer_profile", database.get_record(first)["result"])
        second = self.save(customer=profile(concern="价格"))
        self.save(customer=profile(), owner=self.other)
        with database._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_profiles").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_profile_snapshots").fetchone()[0], 3)
        calendar_store.delete_owned_record_and_tasks(second, self.user["id"])
        with database._connect() as conn:
            row = conn.execute("SELECT concerns_json FROM customer_profiles WHERE owner_id=?", (self.user["id"],)).fetchone()
            self.assertEqual(json.loads(row[0]), ["交期"])
        calendar_store.delete_owned_record_and_tasks(first, self.user["id"])
        with database._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_profiles WHERE owner_id=?", (self.user["id"],)).fetchone()[0], 0)

    def test_unknown_or_abbreviated_identities_do_not_merge(self):
        for name in ("未知", "王总"):
            self.save(customer=profile(name=name))
            self.save(customer=profile(name=name))
        with database._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_profiles").fetchone()[0], 4)

    def test_record_and_profile_rollback_together(self):
        with patch.object(profile_store, "save_snapshot", side_effect=RuntimeError("isolated simulated failure")):
            with self.assertRaises(RuntimeError):
                self.save(customer=profile())
        with database._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_profiles").fetchone()[0], 0)

    def test_server_action_state_survives_stale_edit_and_rejects_forgery(self):
        rid = self.save()
        stale = database.get_record(rid)["result"]
        self.action(rid, "add_ddl_task")
        self.action(rid, "confirm_question", answer="周四")
        stale["reply"] = "新的回复"
        stale["ddl_tasks"][0].update(status="added", calendar_task_id=999999)
        database.update_result(rid, stale)
        fresh = database.get_record(rid)["result"]
        self.assertNotEqual(fresh["ddl_tasks"][0]["calendar_task_id"], 999999)
        self.assertEqual(fresh["questions"][0]["confirmed_answer"], "周四")
        self.assertEqual(calendar_store.list_items(self.user["id"])["total"], 1)


if __name__ == "__main__":
    unittest.main()
