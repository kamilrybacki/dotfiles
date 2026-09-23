import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeJev:
    """In-process stand-in for api.typesafe.ai: records requests, replays canned answers."""

    def __init__(self):
        self.requests: list[dict] = []
        self.answers: dict = {}
        self.status = 200
        self.delay = 0.0

    def handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                if fake.delay:
                    threading.Event().wait(fake.delay)
                answers = fake.answers(body) if callable(fake.answers) else fake.answers
                payload = json.dumps({"model": "jev-test", "answers": answers}).encode()
                self.send_response(fake.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        return Handler


@pytest.fixture()
def fake_jev(monkeypatch, tmp_path):
    fake = FakeJev()
    server = HTTPServer(("127.0.0.1", 0), fake.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("JEV_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("JEV_LOG", str(tmp_path / "decisions.jsonl"))
    import jev_gate.decision_log as log
    monkeypatch.setattr(log, "LOG_PATH", tmp_path / "decisions.jsonl")
    yield fake
    server.shutdown()


@pytest.fixture()
def dead_jev(monkeypatch, tmp_path):
    monkeypatch.setenv("JEV_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    import jev_gate.decision_log as log
    monkeypatch.setattr(log, "LOG_PATH", tmp_path / "decisions.jsonl")
