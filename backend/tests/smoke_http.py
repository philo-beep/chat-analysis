"""真实 Uvicorn + 测试模型替身验证 HTTP 链路/重启；不是 AI 业务验收。"""

from contextlib import contextmanager
import json
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import httpx
from PIL import Image

BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def server(db_path: Path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    bootstrap = """
import sys
from pathlib import Path
import database
database.DB_PATH = Path(sys.argv[1])
import main
from ai_contract import AnalysisOutcome
def fixture(text):
    return {"requirements": [{"field": "数量", "value": "100件", "evidence": "开发引用"}],
            "questions": ["请确认尺码"], "tasks": ["准备方案"], "reply": "收到", "is_sample": True}
main.analyze_chat = fixture
main.analyze_chat_with_source = lambda text, image, mime: AnalysisOutcome(fixture(text), "客户：数量改为150件。")
import uvicorn
uvicorn.run(main.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""
    base = f"http://127.0.0.1:{port}"
    # 使用管道收集少量测试日志，避免 Windows 后台进程继承具名日志文件句柄。
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", bootstrap, str(db_path), str(port)],
        cwd=BACKEND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                output, _ = process.communicate(timeout=10)
                raise RuntimeError(f"Uvicorn exited: {output}")
            try:
                with urlopen(f"{base}/health", timeout=0.5) as response:
                    assert json.load(response) == {"status": "ok"}
                break
            except (URLError, TimeoutError):
                time.sleep(0.1)
        else:
            raise TimeoutError("Uvicorn did not become ready")
        yield base
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=10)


def request(base, method, route, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(base + route, data=data, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response), response.headers


def main():
    with tempfile.TemporaryDirectory(prefix="keyoushu-http-test-") as temp:
        db_path = Path(temp) / "smoke.db"
        text = (BACKEND.parent / "samples/chat-001.txt").read_text(encoding="utf-8")
        with server(db_path) as base:
            assert request(base, "GET", "/health")[:2] == (200, {"status": "ok"})
            status, analyzed, _ = request(base, "POST", "/analyze", {"text": text})
            assert status == 200 and analyzed["is_sample"] is True
            record_id = analyzed["id"]
            status, records, _ = request(base, "GET", "/records")
            assert status == 200 and records[0]["id"] == record_id
            status, record, _ = request(base, "GET", f"/records/{record_id}")
            assert status == 200 and record["text"] == text
            analyzed["requirements"][0]["value"] = "150 件（人工修改）"
            analyzed["reply"] = "数量按150件记录，请再确认尺码和交期。"
            analyzed["is_sample"] = False  # 编辑不能修改来源标记。
            status, saved, _ = request(base, "PUT", f"/records/{record_id}", {"result": analyzed})
            assert status == 200 and saved == {"ok": True}
            status, exported, headers = request(base, "GET", f"/records/{record_id}/export")
            assert status == 200 and exported["result"]["reply"] == analyzed["reply"]
            assert exported["result"]["is_sample"] is True and exported["text"] == text
            assert f"record-{record_id}.json" in headers["Content-Disposition"]
            assert request(base, "POST", "/analyze", {"text": " "})[0] == 400
            assert request(base, "GET", "/records/999999")[0] == 404
            assert request(base, "PUT", f"/records/{record_id}",
                           {"result": {"reply": "missing fields"}})[0] == 422
            status, message_result, _ = request(base, "POST", "/analyze", {"messages": [
                {"role": "customer", "content": "先做100件。"},
                {"role": "seller", "content": "好的。"},
            ]})
            assert status == 200
            status, message_record, _ = request(base, "GET", f'/records/{message_result["id"]}')
            assert status == 200 and message_record["text"].startswith("[客户]")
            assert message_record["source_input"]["messages"][1]["role"] == "seller"
            picture = io.BytesIO()
            Image.new("RGB", (16, 16), "white").save(picture, format="PNG")
            response = httpx.post(base + "/analyze", data={"text": "客户名称：张先生"},
                                  files={"image": ("chat.png", picture.getvalue(), "image/png")}, timeout=10)
            assert response.status_code == 200, response.text
            image_id = response.json()["id"]
            status, image_record, _ = request(base, "GET", f"/records/{image_id}")
            assert status == 200 and image_record["source_image"].startswith("data:image/png;base64,")
            assert image_record["source_transcript"] == "客户：数量改为150件。"
            print("PASS: real HTTP health/analyze/list/detail/edit/export, UTF-8, provenance, 400/404/422")
            print("PASS: real HTTP messages + multipart image upload, original image/transcript persisted (model fixtures)")
        with server(db_path) as base:
            status, reopened, _ = request(base, "GET", f"/records/{record_id}")
            assert status == 200 and reopened["result"]["reply"] == analyzed["reply"]
            assert reopened["result"]["is_sample"] is True
            status, reopened_image, _ = request(base, "GET", f"/records/{image_id}/export")
            assert status == 200 and reopened_image["source_image"] == image_record["source_image"]
            assert reopened_image["source_transcript"] == image_record["source_transcript"]
            print("PASS: Uvicorn process restarted; saved edits and sample flag survived")
        print("PASS: temporary DB only; backend/app.db unchanged")


if __name__ == "__main__":
    main()
