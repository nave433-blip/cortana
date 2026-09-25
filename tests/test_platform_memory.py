"""Round C: memory cores — lifecycle, recall, auto-capture opt-in, export."""
import json

import pytest

import core.config as config_mod


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    import core.memory_cores as mc_mod
    monkeypatch.setattr(mc_mod, "CORES_DIR", tmp_path / "memory" / "cores")
    return tmp_path


def test_remember_recall(isolated):
    from core.memory_cores import remember, recall
    assert remember("facts", "User's dog is named Biscuit.")["ok"]
    assert remember("facts", "User likes dark mode.")["ok"]
    hits = recall("facts", "dog")
    assert len(hits) == 1 and "Biscuit" in hits[0]["text"]
    assert len(recall("facts")) == 2


def test_recall_unknown_core(isolated):
    from core.memory_cores import remember
    assert not remember("nope", "x")["ok"]


def test_forget_by_id_and_text(isolated):
    from core.memory_cores import remember, forget, recall
    r = remember("preferences", "Prefers concise answers.")
    eid = r["entry"]["id"]
    assert forget("preferences", eid)["ok"]
    assert recall("preferences") == []
    remember("preferences", "Likes tabs over spaces.")
    assert forget("preferences", "tabs over spaces")["ok"]
    assert not forget("preferences", "nothing matches this")["ok"]


def test_clear_core_needs_confirmation(isolated, monkeypatch):
    from core.memory_cores import remember, clear_core, recall
    remember("facts", "Something.")
    monkeypatch.setattr("core.approvals.confirm", lambda *a, **k: False)
    assert not clear_core("facts")["ok"]
    assert len(recall("facts")) == 1
    assert clear_core("facts", _confirmed=True)["ok"]
    assert recall("facts") == []


def test_export_core(isolated, tmp_path):
    from core.memory_cores import remember, export_core
    remember("facts", "Export me.")
    dest = tmp_path / "facts.json"
    res = export_core("facts", str(dest))
    assert res["ok"] and res["count"] == 1
    payload = json.loads(dest.read_text())
    assert payload["core"] == "facts"
    assert payload["entries"][0]["text"] == "Export me."


def test_auto_capture_defaults_off(isolated, monkeypatch):
    from core.memory_cores import maybe_auto_capture, recall
    import core.memory_cores as mc_mod
    # No settings override: memory_auto_capture defaults False -> no-op.
    assert maybe_auto_capture("User said hello.") is None
    assert recall("episodic") == []


def test_auto_capture_when_enabled(isolated, monkeypatch):
    import core.memory_cores as mc_mod
    from core.memory_cores import maybe_auto_capture, recall
    monkeypatch.setattr(mc_mod, "auto_capture_enabled", lambda: True)
    res = maybe_auto_capture("User discussed routers.")
    assert res and res["ok"]
    assert any("routers" in e["text"] for e in recall("episodic"))


def test_stats(isolated):
    from core.memory_cores import remember, stats
    remember("facts", "A fact.")
    s = stats()
    assert s["facts"] == 1
    assert s["preferences"] == 0
    assert "vector" in s


def test_scoped_recall(isolated):
    from core.memory_cores import remember, recall
    remember("projects", "API key rotated.", scope="profile:work")
    remember("projects", "Bought milk.", scope="profile:personal")
    assert len(recall("projects", scope="profile:work")) == 1
    assert len(recall("projects")) == 2
