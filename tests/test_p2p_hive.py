"""P2P hive cache + capability registry tests (loopback, no LAN needed).

Verifies the hive_cache_get/put actions, the sharing opt-in gate, and that
the status response advertises capabilities with no key material.
"""
import json
import socket
import threading
import time

import pytest
import requests

import core.config as config_mod
import core.hive as hive
import core.p2p as p2p
from core.p2p import _make_p2p_server


@pytest.fixture()
def isolated_config(tmp_path, monkeypatch):
    fake_file = tmp_path / "config.json"
    monkeypatch.setattr(config_mod, "CONFIG_FILE", fake_file)
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(hive, "CACHE_FILE", tmp_path / "hive_cache.json")
    return tmp_path


@pytest.fixture()
def peer_factory():
    servers = []

    def make():
        httpd = _make_p2p_server(0, bind="127.0.0.1")
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        servers.append(httpd)
        port = httpd.server_address[1]
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                s.close()
                break
            except OSError:
                time.sleep(0.05)
        return httpd, port

    yield make
    for httpd in servers:
        httpd.shutdown()
        httpd.server_close()


def _post(port, action, params):
    return requests.post(
        f"http://127.0.0.1:{port}",
        json={"action": action, "version": p2p.CURRENT_VERSION, **params},
        timeout=5)


def test_cache_actions_disabled_by_default(isolated_config, peer_factory):
    _, port = peer_factory()
    r = _post(port, "hive_cache_get", {"prompt_hash": "abc"})
    assert r.status_code == 403
    r = _post(port, "hive_cache_put",
              {"entry": {"prompt_hash": "abc", "answer": "x"}})
    assert r.status_code == 403


def test_cache_put_then_get(isolated_config, peer_factory, monkeypatch):
    monkeypatch.setattr(hive, "sharing_enabled", lambda: True)
    _, port = peer_factory()
    entry = {"prompt_hash": "deadbeef", "model": "test-model",
             "answer": "the answer", "timestamp": time.time()}
    r = _post(port, "hive_cache_put", {"entry": entry})
    assert r.status_code == 200
    assert r.json()["stored"] is True

    r = _post(port, "hive_cache_get", {"prompt_hash": "deadbeef"})
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["answer"] == "the answer"
    assert entries[0]["model"] == "test-model"
    assert entries[0]["origin"] == "peer:127.0.0.1"


def test_cache_put_rejects_malformed(isolated_config, peer_factory, monkeypatch):
    monkeypatch.setattr(hive, "sharing_enabled", lambda: True)
    _, port = peer_factory()
    r = _post(port, "hive_cache_put", {"entry": {"prompt_hash": "x"}})
    assert r.status_code == 400


def test_cache_put_never_stores_key_material(isolated_config, peer_factory,
                                             monkeypatch):
    monkeypatch.setattr(hive, "sharing_enabled", lambda: True)
    _, port = peer_factory()
    entry = {"prompt_hash": "k1", "model": "m",
             "answer": "a", "timestamp": time.time(),
             "api_key": "sk-should-not-be-stored", "token": "tok-nope"}
    _post(port, "hive_cache_put", {"entry": entry})
    stored = hive.cache_lookup_local_hash("k1")
    assert len(stored) == 1
    blob = json.dumps(stored[0])
    assert "sk-should-not-be-stored" not in blob
    assert "tok-nope" not in blob


def test_status_advertises_capabilities_without_keys(isolated_config,
                                                     peer_factory):
    _, port = peer_factory()
    r = _post(port, "status", {})
    assert r.status_code == 200
    data = r.json()
    caps = data.get("capabilities")
    assert isinstance(caps, dict)
    assert set(caps.keys()) == {"providers", "models", "features", "local_services"}
    assert "hive_cache_get" in caps["features"]
    assert set(caps["local_services"]) == {"scheduler", "dashboard"}
    blob = json.dumps(data).lower()
    for needle in ("sk-", "api_key", "secret"):
        assert needle not in blob
