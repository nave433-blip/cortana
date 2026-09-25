"""Track 2 tests: thin client — resource recommendations, fit refusal,
remote streaming, peer proxy, and the no-keys-to-peers invariant.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

import core.config as config_mod
from tools.ollama_thin import (
    ThinClient, can_fit, detect_resources, fit_explanation, model_ram_need_gb,
    recommend,
)


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    (tmp_path / "config.json").write_text("{}")
    return tmp_path


class FakeRemoteHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/version":
            self._json({"version": "0.11.0"})
        elif self.path == "/api/tags":
            self._json({"models": [{"name": "llama3:latest", "size": 4_000_000_000}]})
        else:
            self._json({}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path == "/api/chat":
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for tok in ["hel", "lo"]:
                self.wfile.write((json.dumps(
                    {"message": {"content": tok}, "done": False}) + "\n").encode())
            self.wfile.write((json.dumps(
                {"message": {"content": ""}, "done": True}) + "\n").encode())
            self.wfile.flush()
        else:
            self._json({}, 404)


@pytest.fixture()
def remote():
    srv = HTTPServer(("127.0.0.1", 0), FakeRemoteHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_detect_resources_shape():
    r = detect_resources()
    assert r["ram_free_gb"] > 0 and r["cpu_count"] >= 1


def test_recommend_tiers():
    assert recommend({"ram_free_gb": 0.8, "ram_total_gb": 2, "cpu_count": 2,
                      "disk_free_gb": 5})["mode"] == "remote"
    assert recommend({"ram_free_gb": 2.5, "ram_total_gb": 4, "cpu_count": 4,
                      "disk_free_gb": 5})["mode"] == "remote-or-tiny"
    assert recommend({"ram_free_gb": 6, "ram_total_gb": 8, "cpu_count": 4,
                      "disk_free_gb": 5})["mode"] == "hybrid"
    assert recommend({"ram_free_gb": 32, "ram_total_gb": 32, "cpu_count": 8,
                      "disk_free_gb": 50})["mode"] == "local"


def test_model_ram_heuristic():
    # 8B params at ~0.58B/param * 1.3 overhead ≈ 6GB
    assert 5.5 < model_ram_need_gb(8) < 6.5


def test_fit_refusal():
    assert can_fit(1_000_000_000, 8_000_000_000) is True
    assert can_fit(6_000_000_000, 8_000_000_000) is False  # >50% of free
    msg = fit_explanation("big:latest", 6_000_000_000, 8_000_000_000)
    assert "REFUSING" in msg and "OOM" in msg


def test_probe_remote(remote, isolated):
    c = ThinClient(remote_host=remote)
    p = c.probe_remote()
    assert p["ok"] is True and p["version"] == "0.11.0"
    bad = ThinClient(remote_host="http://127.0.0.1:1").probe_remote()
    assert bad["ok"] is False


def test_chat_remote_streams_tokens(remote, isolated):
    c = ThinClient(remote_host=remote)
    assert "".join(c.chat("llama3:latest", "hi")) == "hello"


def test_chat_nowhere_is_honest(isolated):
    c = ThinClient()
    out = "".join(c.chat("x", "hi"))
    assert "nowhere to run this" in out


def test_wake_nowhere_is_honest(isolated):
    c = ThinClient()
    r = c.wake("llama3")
    assert r["ok"] is False and "no remote host or peer" in r["error"]


def test_peer_proxy_sends_no_key_material(isolated, monkeypatch):
    seen = {}

    def fake_send(peer_ip, action, params, **kw):
        seen.update(params)
        seen["_action"] = action
        return {"ok": True, "stream": iter([b"tok1\n", b"tok2\n"])}

    # chat_peer imports send_remote_command lazily from core.p2p
    import core.p2p as p2p_mod
    monkeypatch.setattr(p2p_mod, "send_remote_command", fake_send)
    c = ThinClient(peer_ip="127.0.0.1")
    out = "".join(c.chat_peer("llama3", "hello?"))
    assert seen["_action"] == "think"
    blob = json.dumps(seen).lower()
    for needle in ("api_key", "apikey", "secret", "password", "bearer"):
        assert needle not in blob, f"key material leaked: {needle}"
    assert "tok1" in out and "tok2" in out
