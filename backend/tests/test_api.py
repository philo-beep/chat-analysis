"""C 的后端回归测试：只使用临时数据库，不修改 backend/app.db。"""

import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient

import database
import main


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="keyoushu-api-test-")
        self.addCleanup(self.temp_dir.cleanup)
        db_patch = patch.object(database, "DB_PATH", Path(self.temp_dir.name) / "test.db")
        db_patch.start()
        self.addCleanup(db_patch.stop)
        logger_patch = patch.object(main, "logger")
        self.logger = logger_patch.start()
        self.addCleanup(logger_patch.stop)
        self.client = self.enterContext(TestClient(main.app, raise_server_exceptions=False))

    def analyze(self, text="客户甲：我们想定制 100 件文化衫"):
        response = self.client.post("/analyze", json={"text": text})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def result(self, record_id):
        response = self.client.get(f"/records/{record_id}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["result"]

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_full_save_read_edit_export_chain(self):
        text = "  客户甲：我们想定制 100 件文化衫\n数量、预算等待确认。  "
        analyzed = self.analyze(text)
        record_id = analyzed["id"]
        self.assertTrue(analyzed["is_sample"])
        listed = self.client.get("/records").json()
        self.assertEqual(listed[0]["id"], record_id)
        self.assertEqual(set(listed[0]), {"id", "title", "created_at", "updated_at"})
        self.assertEqual(self.client.get(f"/records/{record_id}").json()["text"], text)

        edited = copy.deepcopy(analyzed)
        edited["requirements"][0]["value"] = "150 件（人工修改）"
        edited["reply"] = "收到，修改内容已保存，请再确认预算。"
        edited.pop("is_sample")
        response = self.client.put(f"/records/{record_id}", json={"result": edited})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"ok": True})
        saved = self.result(record_id)
        self.assertEqual(saved["reply"], edited["reply"])
        self.assertTrue(saved["is_sample"])
        self.assertNotIn("id", saved)

        exported = self.client.get(f"/records/{record_id}/export")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()["result"], saved)
        self.assertEqual(exported.json()["text"], text)
        self.assertIn(f'record-{record_id}.json', exported.headers["content-disposition"])
        self.assertIn(edited["reply"], exported.content.decode("utf-8"))

    def test_data_survives_a_new_python_process(self):
        analyzed = self.analyze()
        edited = copy.deepcopy(analyzed)
        edited["reply"] = "重启后仍保留的中文修改"
        self.assertEqual(self.client.put(
            f'/records/{analyzed["id"]}', json={"result": edited}
        ).status_code, 200)
        script = (
            "import json,sys; from pathlib import Path; import database; "
            "database.DB_PATH=Path(sys.argv[1]); database.init_db(); "
            "print(json.dumps(database.get_record(int(sys.argv[2]))))"
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script, str(database.DB_PATH), str(analyzed["id"])],
            cwd=BACKEND, capture_output=True, text=True, timeout=15,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["result"]["reply"], edited["reply"])

    def test_blank_input_rejected_without_saving(self):
        for text in ["", " ", "\n\t"]:
            with self.subTest(text=text):
                response = self.client.post("/analyze", json={"text": text})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["detail"], "聊天原文不能为空")
        self.assertEqual(self.client.get("/records").json(), [])

    def test_invalid_analyze_request(self):
        for payload in [{}, {"text": None}, {"text": 123}, {"text": []}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/analyze", json=payload).status_code, 422)

    def test_missing_record(self):
        valid = {"requirements": [], "questions": [], "tasks": [], "reply": ""}
        responses = [
            self.client.get("/records/999999"),
            self.client.get("/records/999999/export"),
            self.client.put("/records/999999", json={"result": valid}),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "记录不存在"})

    def test_invalid_nested_results_rejected_without_overwriting(self):
        analyzed = self.analyze()
        record_id = analyzed.pop("id")
        bad_changes = [
            {"requirements": "bad"},
            {"requirements": [123]},
            {"requirements": [{"field": "数量", "value": "100"}]},
            {"requirements": [{"field": " ", "value": "100", "evidence": "原文"}]},
            {"requirements": [{"field": "数量", "value": 100, "evidence": "原文"}]},
            {"requirements": [{"field": "数量", "value": "100", "evidence": ""}]},
            {"questions": [123]},
            {"tasks": [{}]},
            {"reply": None},
            {"is_sample": "true"},
        ]
        for change in bad_changes:
            with self.subTest(change=change):
                response = self.client.put(
                    f"/records/{record_id}", json={"result": {**analyzed, **change}}
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.result(record_id), analyzed)
        self.assertEqual(self.client.put(
            f"/records/{record_id}", json={"result": {"reply": "不完整"}}
        ).status_code, 422)

    def test_empty_arrays_and_reply_are_valid(self):
        analyzed = self.analyze()
        empty = {"requirements": [], "questions": [], "tasks": [], "reply": ""}
        response = self.client.put(f'/records/{analyzed["id"]}', json={"result": empty})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.result(analyzed["id"]), {**empty, "is_sample": True})

    def test_sample_origin_cannot_be_changed_by_edit(self):
        analyzed = self.analyze()
        analyzed["is_sample"] = False
        response = self.client.put(f'/records/{analyzed["id"]}', json={"result": analyzed})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.result(analyzed["id"])["is_sample"])

    def test_real_model_origin_cannot_be_changed_by_edit(self):
        real = {"requirements": [], "questions": [], "tasks": [], "reply": "真实结果"}
        with patch.object(main, "analyze_chat", return_value=real):
            analyzed = self.analyze()
        self.assertFalse(analyzed["is_sample"])
        analyzed["is_sample"] = True
        self.assertEqual(self.client.put(
            f'/records/{analyzed["id"]}', json={"result": analyzed}
        ).status_code, 200)
        self.assertFalse(self.result(analyzed["id"])["is_sample"])

    def test_legacy_missing_origin_is_not_invented(self):
        legacy = {"requirements": [], "questions": [], "tasks": [], "reply": "旧记录"}
        record_id = database.save_record("旧原文", legacy)
        edited = {**legacy, "reply": "修改旧记录", "is_sample": False}
        self.assertEqual(self.client.put(
            f"/records/{record_id}", json={"result": edited}
        ).status_code, 200)
        self.assertNotIn("is_sample", self.result(record_id))

    def test_model_failures_return_json_without_saving(self):
        failures = [
            (NotImplementedError("internal detail"), "真实模型调用尚未实现"),
            (TimeoutError("internal detail"), "模型调用超时"),
            (RuntimeError("private upstream detail"), "模型调用失败"),
        ]
        for error, expected in failures:
            with self.subTest(error=type(error).__name__):
                with patch.object(main, "analyze_chat", side_effect=error):
                    response = self.client.post("/analyze", json={"text": "有效输入"})
                self.assertEqual(response.status_code, 500)
                self.assertIn(expected, response.json()["detail"])
                self.assertNotIn("internal detail", response.text)
                self.assertNotIn("private upstream detail", response.text)
        self.assertEqual(self.client.get("/records").json(), [])
        self.assertTrue(self.logger.exception.called)

    def test_invalid_model_result_is_not_saved(self):
        for bad in [None, [], {"reply": "字段缺失"},
                    {"requirements": [], "questions": [123], "tasks": [], "reply": ""}]:
            with self.subTest(result=bad):
                with patch.object(main, "analyze_chat", return_value=bad):
                    response = self.client.post("/analyze", json={"text": "有效输入"})
                self.assertEqual(response.status_code, 500)
                self.assertIn("格式不符合", response.json()["detail"])
        self.assertEqual(self.client.get("/records").json(), [])

    def test_real_model_evidence_must_exist_in_original(self):
        real = {"requirements": [{"field": "数量", "value": "150件", "evidence": "虚构原文"}],
                "questions": [], "tasks": [], "reply": ""}
        with patch.object(main, "analyze_chat", return_value=real):
            response = self.client.post("/analyze", json={"text": "数量改为150件"})
            self.assertEqual(response.status_code, 500)
            self.assertIn("原文引用无效", response.json()["detail"])
            real["requirements"][0]["evidence"] = "数量改为150件"
            response = self.client.post("/analyze", json={"text": "  数量改为150件  "})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.client.get("/records").json()), 1)

    def test_model_cannot_override_saved_record_id(self):
        result = {"requirements": [], "questions": [], "tasks": [], "reply": "", "id": 999999}
        with patch.object(main, "analyze_chat", return_value=result):
            analyzed = self.analyze()
        self.assertNotEqual(analyzed["id"], 999999)
        self.assertEqual(self.client.get(f'/records/{analyzed["id"]}').status_code, 200)

    def test_input_trimmed_for_analysis_but_original_preserved(self):
        with patch.object(main, "analyze_chat", return_value={
            "requirements": [], "questions": [], "tasks": [], "reply": ""
        }) as model:
            analyzed = self.analyze("  客户甲：数量待确认\n  ")
        model.assert_called_once_with("客户甲：数量待确认")
        self.assertEqual(self.client.get(f'/records/{analyzed["id"]}').json()["text"],
                         "  客户甲：数量待确认\n  ")

    def test_database_errors_return_diagnostic_json(self):
        with patch.object(database, "list_records", side_effect=sqlite3.OperationalError("disk error")):
            response = self.client.get("/records")
        self.assertEqual(response.status_code, 500)
        self.assertIn("数据库操作失败", response.json()["detail"])
        self.assertTrue(self.logger.error.called)

    def test_failed_save_does_not_report_success(self):
        with patch.object(database, "save_record", side_effect=sqlite3.OperationalError("disk error")):
            response = self.client.post("/analyze", json={"text": "有效输入"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("数据库操作失败", response.json()["detail"])
        self.assertEqual(self.client.get("/records").json(), [])

    def test_failed_edit_keeps_previous_result(self):
        analyzed = self.analyze()
        original = self.result(analyzed["id"])
        edited = {**analyzed, "reply": "不应保存"}
        with patch.object(database, "update_result", side_effect=sqlite3.OperationalError("disk error")):
            response = self.client.put(f'/records/{analyzed["id"]}', json={"result": edited})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.result(analyzed["id"]), original)

    def test_record_disappearing_during_edit_returns_404(self):
        analyzed = self.analyze()
        with patch.object(database, "update_result", return_value=False):
            response = self.client.put(f'/records/{analyzed["id"]}', json={"result": analyzed})
        self.assertEqual(response.status_code, 404)

    def test_corrupt_record_has_clear_error(self):
        analyzed = self.analyze()
        for corrupt in ["not JSON", "[]", "null"]:
            with self.subTest(corrupt=corrupt):
                with database._connect() as connection:
                    connection.execute("UPDATE records SET result=? WHERE id=?", (corrupt, analyzed["id"]))
                for route in [f'/records/{analyzed["id"]}', f'/records/{analyzed["id"]}/export']:
                    response = self.client.get(route)
                    self.assertEqual(response.status_code, 500)
                    self.assertIn("历史记录内容损坏", response.json()["detail"])

    def test_cors_allows_local_frontend(self):
        for origin in ["http://127.0.0.1:5173", "http://localhost:5173"]:
            with self.subTest(origin=origin):
                response = self.client.options("/analyze", headers={
                    "Origin": origin, "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_database_connection_is_closed(self):
        with database._connect() as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_failed_transaction_is_rolled_back(self):
        with self.assertRaises(RuntimeError):
            with database._connect() as connection:
                connection.execute(
                    "INSERT INTO records (text,result,created_at,updated_at) VALUES (?,?,?,?)",
                    ("不应保留", "{}", "now", "now"),
                )
                raise RuntimeError("rollback test")
        self.assertEqual(database.list_records(), [])


if __name__ == "__main__":
    unittest.main()
