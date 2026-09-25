"""Track 1 tests: Ollama fleet management — real disk accounting, prune,
routing, warm, stats, bench, Modelfile/GGUF, auto-pull. All HTTP mocked
with a fake Ollama server on loopback; config isolated per test.
"""
import base64
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import core.config as config_mod
from core.ollama_mgmt import (
    OllamaHost, OllamaManager, handle_ollama_args, manifest_disk_usage,
    note_chat_usage,
)


class FakeOllamaHandler(BaseHTTPRequestHandler):
    server_state = None  # set per-test: {"digests": {}, "deleted": [], "created": []}

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ndjson(self, lines):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for ln in lines:
            self.wfile.write((json.dumps(ln) + "\n").encode())
        self.wfile.flush()

    def do_GET(self):
        st = self.server_state
        if self.path == "/api/version":
            self._json({"version": "0.11.0"})
        elif self.path == "/api/tags":
            models = []
            for name, digest in st["digests"].items():
                models.append({"name": name, "model": name, "size": 4_000_000_000,
                               "digest": digest, "modified_at": "2026-01-01T00:00:00Z",
                               "details": {}})
            self._json({"models": models})
        elif self.path == "/api/ps":
            self._json({"models": st.get("loaded", [])})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        st = self.server_state
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/show":
            self._json({"modelfile": f"FROM {body.get('name')}", "details": {}})
        elif self.path == "/api/generate":
            self._json({"model": body.get("model"), "response": "ok",
                        "eval_count": 64, "eval_duration": 2_000_000_000,
                        "prompt_eval_count": 10, "prompt_eval_duration": 100_000_000,
                        "total_duration": 2_100_000_000, "done": True})
        elif self.path == "/api/chat":
            self._json({"model": body.get("model"),
                        "message": {"role": "assistant", "content": "pong"},
                        "done": True, "prompt_eval_count": 5, "eval_count": 3,
                        "total_duration": 500_000_000})
        elif self.path == "/api/pull":
            st["digests"][body.get("name")] = "sha256:NEW" + body.get("name", "")
            self._ndjson([{"status": "pulling manifest"}, {"status": "success"}])
        elif self.path == "/api/create":
            st["created"].append(body.get("name"))
            self._ndjson([{"status": "creating"}, {"status": "success"}])
        else:
            self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        st = self.server_state
        if self.path == "/api/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            st["deleted"].append(body.get("name"))
            st["digests"].pop(body.get("name"), None)
            self._json({})
        else:
            self._json({"error": "not found"}, 404)


@pytest.fixture()
def ollama_server():
    state = {"digests": {"llama3:latest": "sha256:AAA", "tiny:latest": "sha256:BBB"},
             "deleted": [], "created": [], "loaded": []}
    FakeOllamaHandler.server_state = state
    srv = HTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield url, state
    srv.shutdown()


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    (tmp_path / "config.json").write_text("{}")
    return tmp_path


@pytest.fixture()
def mgr(isolated, ollama_server):
    url, state = ollama_server
    (isolated / "config.json").write_text(json.dumps({"ollama_hosts": [url]}))
    return OllamaManager(), url, state


def test_disk_accounting_from_real_manifests(tmp_path, monkeypatch):
    base = tmp_path / "models"
    mf_dir = base / "manifests" / "registry.ollama.ai" / "library" / "llama3"
    mf_dir.mkdir(parents=True)
    blob_dir = base / "blobs"
    blob_dir.mkdir()
    blob_a = blob_dir / "sha256-aaa"
    blob_a.write_bytes(b"x" * 1000)
    blob_b = blob_dir / "sha256-bbb"
    blob_b.write_bytes(b"y" * 2500)
    (mf_dir / "latest").write_text(json.dumps({
        "config": {"digest": "sha256:aaa"},
        "layers": [{"digest": "sha256:bbb"}]}))
    monkeypatch.setenv("OLLAMA_MODELS", str(base))
    usage = manifest_disk_usage()
    assert usage["llama3:latest"] == 3500


def test_disk_accounting_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path / "nope"))
    assert manifest_disk_usage() == {}


def test_library_and_stale(mgr):
    m, url, state = mgr
    rows = m.library()
    names = {r["name"] for r in rows if "error" not in r}
    assert names == {"llama3:latest", "tiny:latest"}
    # no usage history and old modified_at -> stale
    assert all(r["stale"] for r in rows if "error" not in r)


def test_prune_dry_run_deletes_nothing(mgr, capsys):
    m, url, state = mgr
    cands = m.prune(dry_run=True)
    assert set(cands) == {"llama3:latest", "tiny:latest"}
    assert state["deleted"] == []  # dry run touched nothing
    # tracked models are never prune candidates
    m.track("llama3:latest")
    cands2 = m.prune(dry_run=True)
    assert cands2 == ["tiny:latest"]


def test_route_picks_host_with_model(isolated, ollama_server):
    url, state = ollama_server
    (isolated / "config.json").write_text(
        json.dumps({"ollama_hosts": ["http://127.0.0.1:1", url]}))
    m = OllamaManager()
    assert m.route("llama3:latest") == url
    assert m.route("nope:latest") is None


def test_add_host_unreachable(isolated):
    (isolated / "config.json").write_text(json.dumps({"ollama_hosts": []}))
    m = OllamaManager()
    r = m.add_host("http://127.0.0.1:1")
    assert r["ok"] is False


def test_bench_tokens_per_sec(mgr):
    m, url, state = mgr
    b = m.bench("llama3:latest")
    assert b["ok"] is True
    assert b["tokens_per_sec"] == 32.0  # 64 tokens / 2.0s


def test_note_usage_and_stats(mgr):
    m, url, state = mgr
    note_chat_usage("llama3:latest", url,
                    {"prompt_eval_count": 10, "eval_count": 20, "total_duration": 1_000_000_000})
    m2 = OllamaManager()  # fresh read, like a new CLI invocation
    stats = m2.stats("llama3:latest")
    assert stats["llama3:latest"]["calls"] == 1
    assert stats["llama3:latest"]["completion"] == 20
    assert stats["llama3:latest"]["avg_tps"] == 20.0


def test_warm_records_last_used(mgr):
    m, url, state = mgr
    # server has no /api/chat keep_alive issue; warm uses chat
    r = m.warm("tiny:latest", keep_alive="5m")
    assert r["ok"] is True
    assert m._model_state("tiny:latest")["last_used"] > 0


def test_modelfile_template(mgr):
    m, url, state = mgr
    mf = m.build_modelfile("llama3", system="Be terse.", temperature=0.5)
    assert mf.startswith("FROM llama3")
    assert 'SYSTEM """' in mf and "Be terse." in mf
    assert "PARAMETER temperature 0.5" in mf


def test_gguf_import_validates_magic(mgr, tmp_path):
    m, url, state = mgr
    bad = tmp_path / "bad.gguf"
    bad.write_bytes(b"NOTG" + b"\x00" * 100)
    r = m.import_gguf(str(bad), "bad-model")
    assert r["ok"] is False and "magic" in r["error"]
    good = tmp_path / "good.gguf"
    good.write_bytes(b"GGUF" + b"\x00" * 100)
    r = m.import_gguf(str(good), "good-model")
    assert r["ok"] is True
    assert "good-model" in state["created"]


def test_track_and_auto_pull_digest_change(mgr, capsys):
    m, url, state = mgr
    m.track("llama3:latest")
    results = m.auto_pull()
    assert len(results) == 1
    assert results[0]["changed"] is True
    assert results[0]["before"] != results[0]["after"]


def test_handle_ollama_args_routing(isolated):
    assert handle_ollama_args("run llama3") is False  # passthrough
    assert handle_ollama_args("list --bogus-flag-xyz") is True  # managed
    assert handle_ollama_args("") is True  # help
