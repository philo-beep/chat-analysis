"""C 的后端回归测试：只使用临时数据库，不修改 backend/app.db。"""

import copy
import base64
import io
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import ANY, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient
from PIL import Image

import database
import auth_store
import main
from ai_contract import AnalysisOutcome


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="keyoushu-api-test-")
        self.addCleanup(self.temp_dir.cleanup)
        db_patch = patch.object(database, "DB_PATH", Path(self.temp_dir.name) / "test.db")
        db_patch.start()
        self.addCleanup(db_patch.stop)
        secret_patch = patch.dict(os.environ, {
            "KEYOUSHU_JWT_SECRET": "api-test-only-75cfe97279054a378196ff529ae231b2",
        })
        secret_patch.start()
        self.addCleanup(secret_patch.stop)
        logger_patch = patch.object(main, "logger")
        self.logger = logger_patch.start()
        self.addCleanup(logger_patch.stop)
        # 接口回归使用固定替身，与 D 的运行模式和真实模型依赖隔离。
        model_patch = patch.object(main, "analyze_chat", return_value={
            "requirements": [{"field": "数量", "value": "100 件", "evidence": "开发引用"}],
            "questions": ["请确认尺码"], "tasks": ["准备方案"], "reply": "收到", "is_sample": True,
        })
        model_patch.start()
        self.addCleanup(model_patch.stop)
        self.client = self.enterContext(TestClient(main.app, raise_server_exceptions=False))
        # 使用临时库中的真实账号和登录接口，不覆盖鉴权依赖。
        auth_store.create_user("testadmin", "Test-admin-987654!", role_codes=["admin"])
        logged_in = self.client.post("/api/auth/login", json={
            "username": "testadmin", "password": "Test-admin-987654!",
        })
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        self.client.headers["Authorization"] = f"Bearer {logged_in.json()['data']['token']}"

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

    def test_unauthenticated_text_and_image_never_reach_model(self):
        token = self.client.headers.pop("Authorization")
        try:
            with patch.object(main, "analyze_chat") as text_model, patch.object(main, "analyze_chat_with_source") as image_model:
                for authorization in (None, "Bearer not-a-valid-token"):
                    with self.subTest(authorization=authorization):
                        headers = {} if authorization is None else {"Authorization": authorization}
                        response = self.client.post("/analyze", json={"text": "客户：需要100件文化衫。"}, headers=headers)
                        self.assertEqual(response.status_code, 401, response.text)
                        response = self.client.post("/analyze", files={
                            "image": ("chat.png", self.image_bytes(), "image/png"),
                        }, headers=headers)
                        self.assertEqual(response.status_code, 401, response.text)
                text_model.assert_not_called()
                image_model.assert_not_called()
        finally:
            self.client.headers["Authorization"] = token
        self.assertEqual(database.list_records(), [])

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
        model.assert_called_once_with("客户甲：数量待确认", profile_resolver=ANY)
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

    def test_messages_preserve_original_and_forward_roles_and_time(self):
        payload = {"messages": [
            {"speaker": "张先生", "role": "customer", "content": "  先做100件。  ", "time": "10:01"},
            {"role": "seller", "text": "可以的。", "timestamp": "10:02"},
            "数量改成150件",
        ]}
        result = {"requirements": [{"field": "数量", "value": "150件", "evidence": "数量改成150件"}],
                  "questions": [], "tasks": [], "reply": "收到"}
        with patch.object(main, "analyze_chat", return_value=result) as model:
            response = self.client.post("/analyze", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        model.assert_called_once_with("[10:01 客户(张先生)] 先做100件。\n[10:02 商家] 可以的。\n[未标注] 数量改成150件", profile_resolver=ANY)
        detail = self.client.get(f'/records/{response.json()["id"]}').json()
        self.assertEqual(detail["source_input"], payload)
        self.assertEqual(detail["text"], model.call_args.args[0])
        self.assertEqual(set(response.json()), {"id", "requirements", "questions", "tasks", "reply", "is_sample"})

    def test_messages_invalid_inputs_fail_without_model_call(self):
        cases = [
            ({"messages": []}, 400), ({"messages": [" "]}, 400),
            ({"messages": [{}]}, 400),
            ({"messages": [{"content": "", "text": "不得回退"}]}, 400),
            ({"messages": [123]}, 422),
            ({"messages": [{"content": 123}]}, 422),
            ({"messages": [{"role": 123, "content": "hello"}]}, 422),
            ({"text": "hello", "messages": ["hi"]}, 422),
        ]
        with patch.object(main, "analyze_chat") as model:
            for payload, status in cases:
                with self.subTest(payload=payload):
                    response = self.client.post("/analyze", json=payload)
                    self.assertEqual(response.status_code, status, response.text)
        model.assert_not_called()
        self.assertEqual(database.list_records(), [])

    @staticmethod
    def image_bytes(format="PNG"):
        output = io.BytesIO()
        Image.new("RGB", (16, 16), "white").save(output, format=format)
        return output.getvalue()

    def upload(self, image_bytes=None, mime="image/png", text="", filename="chat.png"):
        return self.client.post("/analyze", data={"text": text}, files={
            "image": (filename, self.image_bytes() if image_bytes is None else image_bytes, mime),
        })

    def test_image_forwarded_and_original_transcript_survive_edit_export(self):
        image_bytes = self.image_bytes()
        transcript = "客户：数量改成150件。\n商家：收到。"
        result = {"requirements": [{"field": "数量", "value": "150件", "evidence": "数量改成150件"}],
                  "questions": [], "tasks": [], "reply": "收到"}
        original_text = "  客户名称：张先生\n  "
        with patch.object(main, "analyze_chat_with_source", return_value=AnalysisOutcome(result, transcript)) as model:
            response = self.upload(image_bytes, text=original_text)
        self.assertEqual(response.status_code, 200, response.text)
        model.assert_called_once_with(original_text.strip(), image_bytes, "image/png", profile_resolver=ANY)
        self.assertEqual(set(response.json()), {"id", "requirements", "questions", "tasks", "reply", "is_sample"})
        record_id = response.json()["id"]
        detail = self.client.get(f"/records/{record_id}").json()
        self.assertEqual(detail["text"], original_text + "\n\n[聊天截图转录]\n" + transcript)
        self.assertEqual(detail["source_transcript"], transcript)
        self.assertEqual(detail["source_input"], {"text": original_text})
        self.assertEqual(base64.b64decode(detail["source_image"].split(",")[1]), image_bytes)
        self.assertEqual(self.client.put(f"/records/{record_id}", json={"result": {
            **result, "reply": "人工修改", "is_sample": True,
        }}).status_code, 200)
        exported = self.client.get(f"/records/{record_id}/export").json()
        for key in ["text", "source_input", "source_image", "source_transcript"]:
            self.assertEqual(exported[key], detail[key])
        self.assertEqual(exported["result"]["reply"], "人工修改")
        self.assertFalse(exported["result"]["is_sample"])

    def test_image_only_jpeg_and_webp_are_valid(self):
        outcome = AnalysisOutcome({"requirements": [], "questions": [], "tasks": [], "reply": ""}, "客户：想了解文化衫")
        for format, mime in [("JPEG", "image/jpeg"), ("WEBP", "image/webp")]:
            with self.subTest(format=format), patch.object(main, "analyze_chat_with_source", return_value=outcome):
                response = self.upload(self.image_bytes(format), mime, filename="screenshot")
                self.assertEqual(response.status_code, 200, response.text)

    def test_invalid_images_do_not_call_model_or_save(self):
        cases = [
            (b"", "image/png", 400), (b"not an image", "image/png", 400),
            (self.image_bytes("GIF"), "image/gif", 415),
            (self.image_bytes(), "image/jpeg", 415),
            (self.image_bytes()[:30], "image/png", 400),
            (b"x" * (main.MAX_IMAGE_BYTES + 1), "image/png", 413),
        ]
        with patch.object(main, "analyze_chat_with_source") as model:
            for data, mime, status in cases:
                with self.subTest(mime=mime, size=len(data)):
                    response = self.upload(data, mime)
                    self.assertEqual(response.status_code, status, response.text)
            with patch.object(main, "MAX_IMAGE_PIXELS", 10):
                self.assertEqual(self.upload().status_code, 413)
        model.assert_not_called()
        self.assertEqual(database.list_records(), [])

    def test_bad_image_model_outcome_or_failure_is_not_saved(self):
        empty = {"requirements": [], "questions": [], "tasks": [], "reply": ""}
        outcomes = [None, AnalysisOutcome(empty, " "), AnalysisOutcome({"reply": "bad"}, "客户：你好"),
                    AnalysisOutcome({**empty, "requirements": [{"field": "预算", "value": "5000元", "evidence": "捏造引用"}]}, "客户：你好")]
        for outcome in outcomes:
            with self.subTest(outcome=outcome), patch.object(main, "analyze_chat_with_source", return_value=outcome):
                response = self.upload()
                self.assertEqual(response.status_code, 500, response.text)
        with patch.object(main, "analyze_chat_with_source", side_effect=TimeoutError("private detail")):
            response = self.upload()
            self.assertEqual(response.status_code, 500)
            self.assertIn("超时", response.json()["detail"])
            self.assertNotIn("private detail", response.text)
        self.assertEqual(database.list_records(), [])

    def test_bad_transport_returns_friendly_error(self):
        self.assertEqual(self.client.post("/analyze", content="{bad", headers={"Content-Type": "application/json"}).status_code, 400)
        self.assertEqual(self.client.post("/analyze", content="hello", headers={"Content-Type": "text/plain"}).status_code, 415)
        response = self.client.post("/analyze", data={"text": "x", "other": "x"}, files={"image": ("chat.png", self.image_bytes(), "image/png")})
        self.assertEqual(response.status_code, 422)
        response = self.client.post("/analyze", files=[
            ("image", (None, "ignored")),
            ("image", ("chat.png", self.image_bytes(), "image/png")),
        ])
        self.assertEqual(response.status_code, 422)

    def test_old_database_migrates_without_losing_records(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        legacy_result = {"requirements": [], "questions": [], "tasks": [], "reply": "历史结果"}
        with closing(sqlite3.connect(legacy_path)) as connection, connection:
            connection.execute("CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL DEFAULT '', text TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            connection.execute("INSERT INTO records (text,result,created_at,updated_at) VALUES (?,?,?,?)", ("历史原文", json.dumps(legacy_result), "old", "old"))
        with patch.object(database, "DB_PATH", legacy_path):
            database.init_db()
            database.init_db()
            record = database.get_record(1)
            self.assertEqual(record["text"], "历史原文")
            self.assertEqual(record["result"], legacy_result)
            self.assertIsNone(record["source_input"])
            self.assertIsNone(record["source_image"])
            self.assertEqual(record["source_transcript"], "")
            self.assertEqual(database.save_record("新记录", legacy_result), 2)


if __name__ == "__main__":
    unittest.main()
