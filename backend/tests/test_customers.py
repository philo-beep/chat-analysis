"""Customer ownership, snapshot history, migration, and stale-context rollback."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import auth_store
import calendar_store
import database
import main
import profile_store


def profile(**changes):
    value = {"display_name": "林晓", "role": "采购", "company": "云杉公司", "industry": "零售",
             "concerns": ["交期"], "decision_style": "内部确认", "communication_preferences": ["文字沟通"],
             "risk_points": [], "next_follow_up": "准备报价", "communication_strategy": "先确认交期，再提供分档报价。",
             "communication_points": ["确认交付时间", "给出分档报价", "询问审批进度"]}
    value.update(changes)
    return value


class CustomerTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix="keyoushu-customers-"))
        self.enterContext(patch.object(database, "DB_PATH", Path(directory) / "test.db"))
        self.enterContext(patch.dict(os.environ, {"KEYOUSHU_JWT_SECRET": "customer-test-only-secret-at-least-32-characters"}))
        self.client = self.enterContext(TestClient(main.app, raise_server_exceptions=False))
        self.user = auth_store.create_user("customer_owner", "Customer-test-2026", ["member"])
        self.other = auth_store.create_user("customer_other", "Customer-test-2026", ["admin"])
        self.headers = self.login("customer_owner")
        self.other_headers = self.login("customer_other")

    def login(self, username):
        response = self.client.post("/api/auth/login", json={"username": username, "password": "Customer-test-2026"})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": "Bearer " + response.json()["data"]["token"]}

    def save(self, customer=None, **kwargs):
        return database.save_record("客户：请准备报价。", {"requirements": [], "questions": [], "tasks": [], "reply": "收到"},
                                    owner_id=self.user["id"], customer_profile=customer or profile(), **kwargs)

    def listing(self, **params):
        response = self.client.get("/api/customers", params=params, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def test_list_search_order_pagination_and_literal_search(self):
        self.assertEqual(self.listing()["total"], 0)
        self.save()
        self.save(profile(display_name="陈明", company="星河公司"))
        self.save(profile(next_follow_up="核实新交期"))
        result = self.listing(limit=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["items"][0]["display_name"], "林晓")
        self.assertEqual(result["items"][0]["snapshot_count"], 2)
        self.assertIn("last_analyzed_at", result["items"][0])
        self.assertNotIn("owner_id", result["items"][0])
        self.assertNotIn("identity_key", result["items"][0])
        self.assertEqual(self.listing(q="云杉")["total"], 1)
        self.assertEqual(self.listing(q="陈明")["total"], 1)
        self.assertEqual(self.listing(q="%")["total"], 0)
        self.assertEqual(self.listing(q="_")["total"], 0)
        self.assertEqual(self.listing(limit=1, offset=1)["items"][0]["display_name"], "陈明")

    def test_details_history_and_admin_cannot_cross_owner(self):
        self.save()
        self.save(profile(communication_strategy="先核实预算。", concerns=["价格"]))
        customer_id = self.listing()["items"][0]["id"]
        detail_url = f"/api/customers/{customer_id}"
        current = self.client.get(detail_url, headers=self.headers).json()["data"]
        self.assertEqual(current["profile"]["communication_strategy"], "先核实预算。")
        timeline = self.client.get(detail_url + "/snapshots", headers=self.headers).json()["data"]
        self.assertEqual(timeline["total"], 2)
        snapshot_id = timeline["items"][-1]["id"]
        snapshot_url = detail_url + f"/snapshots/{snapshot_id}"
        old = self.client.get(snapshot_url, headers=self.headers).json()["data"]
        self.assertEqual(old["profile"]["concerns"], ["交期"])
        self.assertEqual(self.client.get(detail_url, headers=self.headers).json()["data"]["profile"]["concerns"], ["价格"])
        self.assertEqual(self.client.get("/api/customers", headers=self.other_headers).json()["data"]["total"], 0)
        for url in (detail_url, detail_url + "/snapshots", snapshot_url):
            response = self.client.get(url, headers=self.other_headers)
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(response.json()["code"], 404)
        self.assertEqual(self.client.get("/api/customers").status_code, 401)

    def test_context_uses_exact_owner_identity_and_stale_update_rolls_back(self):
        self.save()
        context = profile_store.context_for_identity(self.user["id"], {"display_name": " 林 晓 ", "company": "云杉公司"})
        self.assertEqual(context["profile"]["display_name"], "林晓")
        self.assertNotIn("version", context["profile"])
        self.assertIsNone(profile_store.context_for_identity(self.other["id"], profile())["profile"])
        self.assertIsNone(profile_store.context_for_identity(self.user["id"], profile(display_name="林总"))["profile"])
        self.save(profile(concerns=["交期", "价格"]), profile_context=context)
        with self.assertRaises(profile_store.ProfileConflictError):
            self.save(profile(concerns=["质量"]), profile_context=context)
        self.assertEqual(self.listing()["items"][0]["snapshot_count"], 2)
        with database._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 2)

    def test_new_identity_race_and_history_delete_restore_guidance(self):
        context = profile_store.context_for_identity(self.user["id"], profile())
        first = self.save(profile_context=context)
        with self.assertRaises(profile_store.ProfileConflictError):
            self.save(profile_context=context)
        latest_context = profile_store.context_for_identity(self.user["id"], profile())
        second = self.save(profile(communication_strategy="先谈方案。"), profile_context=latest_context)
        calendar_store.delete_owned_record_and_tasks(second, self.user["id"])
        self.assertEqual(self.listing()["items"][0]["communication_strategy"], profile()["communication_strategy"])
        calendar_store.delete_owned_record_and_tasks(first, self.user["id"])
        self.assertEqual(self.listing()["total"], 0)

    def test_old_snapshot_fields_are_empty_and_migration_is_idempotent(self):
        old = profile()
        old.pop("communication_strategy")
        old.pop("communication_points")
        self.save(old)
        with database._connect() as conn:
            conn.execute("UPDATE customer_profile_snapshots SET snapshot_json=?", (json.dumps(old),))
        database.init_db()
        database.init_db()
        customer = self.listing()["items"][0]
        self.assertEqual(customer["communication_strategy"], "")
        self.assertEqual(customer["communication_points"], [])
        snapshots = profile_store.list_snapshots(self.user["id"], customer["id"])
        snapshot = profile_store.get_snapshot(self.user["id"], customer["id"], snapshots["items"][0]["id"])
        self.assertEqual(snapshot["profile"]["communication_strategy"], "")
        self.assertEqual(snapshot["profile"]["communication_points"], [])
        self.assertEqual(snapshots["total"], 1)

    def test_invalid_parameters_and_cross_customer_snapshot(self):
        self.save()
        self.save(profile(display_name="陈明", company="星河公司"))
        first, second = self.listing()["items"]
        snapshot = profile_store.list_snapshots(self.user["id"], first["id"])["items"][0]
        response = self.client.get(f"/api/customers/{second['id']}/snapshots/{snapshot['id']}", headers=self.headers)
        self.assertEqual(response.status_code, 404)
        for path in ("/api/customers?limit=0", "/api/customers?offset=-1", "/api/customers/0", "/api/customers/1/snapshots/0"):
            self.assertEqual(self.client.get(path, headers=self.headers).status_code, 422)


if __name__ == "__main__":
    unittest.main()
