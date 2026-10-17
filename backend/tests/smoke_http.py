"""通过真实 Uvicorn 进程验证 HTTP 链路和服务重启；仅使用临时数据库。"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def server(db_path: Path, log_path: Path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    bootstrap = (
        "import sys; from pathlib import Path; import database; "
        "database.DB_PATH=Path(sys.argv[1]); import uvicorn; "
        "uvicorn.run('main:app',host='127.0.0.1',port=int(sys.argv[2]),log_level='warning')"
    )
    base = f"http://127.0.0.1:{port}"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", bootstrap, str(db_path), str(port)],
            cwd=BACKEND, stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f"Uvicorn exited: {log_path.read_text(encoding='utf-8')}")
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
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


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
        log_path = Path(temp) / "server.log"
        text = (BACKEND.parent / "samples/chat-001.txt").read_text(encoding="utf-8")
        with server(db_path, log_path) as base:
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
            print("PASS: real HTTP health/analyze/list/detail/edit/export, UTF-8, provenance, 400/404/422")
        with server(db_path, log_path) as base:
            status, reopened, _ = request(base, "GET", f"/records/{record_id}")
            assert status == 200 and reopened["result"]["reply"] == analyzed["reply"]
            assert reopened["result"]["is_sample"] is True
            print("PASS: Uvicorn process restarted; saved edits and sample flag survived")
        print("PASS: temporary DB only; backend/app.db unchanged")


if __name__ == "__main__":
    main()
