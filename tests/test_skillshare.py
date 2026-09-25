"""Track 3b tests: skill sharing — pack/verify/install/tamper/offer.

Config isolated; Confirm prompts monkeypatched. run_skill executes a tiny
script through the real sandbox on Linux.
"""
import base64
import json
import zipfile

import pytest

import core.config as config_mod
import core.skillshare as skillshare


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(skillshare, "_skills_dir",
                        lambda: tmp_path / "skills", raising=False)
    (tmp_path / "config.json").write_text("{}")
    return tmp_path


@pytest.fixture()
def skill_dir(tmp_path):
    d = tmp_path / "demo-skill"
    d.mkdir()
    (d / "skill.json").write_text(json.dumps({
        "name": "demo", "version": "1.0", "description": "demo skill",
        "author": "tester", "entry": "run.sh", "permissions": []}))
    (d / "run.sh").write_text("#!/bin/sh\necho skill-ran-ok\n")
    (d / "prompt.md").write_text("# demo prompt\n")
    return d


@pytest.fixture()
def packed(isolated, skill_dir, tmp_path):
    zp, manifest = skillshare.pack_skill(str(skill_dir), str(tmp_path / "demo.zip"))
    return zp, manifest


def test_pack_and_verify(packed):
    zp, manifest = packed
    assert manifest["name"] == "demo"
    assert len(manifest["pack_sha256"]) == 64
    v = skillshare.verify_pack(zp)
    assert v["ok"] is True and v["tampered"] == []


def test_tamper_detected(packed, tmp_path):
    zp, manifest = packed
    # rewrite one file inside the zip -> hashes no longer match
    data = bytearray(open(zp, "rb").read())
    with zipfile.ZipFile(zp, "a") as zf:
        zf.writestr("evil.txt", "evil")
    v = skillshare.verify_pack(zp)
    assert v["ok"] is False


def test_install_shows_and_installs(packed, isolated, monkeypatch):
    zp, manifest = packed
    monkeypatch.setattr(skillshare.Confirm, "ask", lambda *a, **k: True)
    r = skillshare.install_skill(zp)
    assert r["ok"] is True
    assert (isolated / "skills" / "demo" / "skill.json").is_file()
    assert any(s["name"] == "demo" for s in skillshare.list_skills())


def test_install_cancelled(packed, isolated, monkeypatch):
    zp, manifest = packed
    monkeypatch.setattr(skillshare.Confirm, "ask", lambda *a, **k: False)
    r = skillshare.install_skill(zp)
    assert r["ok"] is False
    assert not (isolated / "skills" / "demo").exists()


def test_install_refuses_tampered(packed, isolated, monkeypatch):
    zp, manifest = packed
    with zipfile.ZipFile(zp, "a") as zf:
        zf.writestr("evil.txt", "evil")
    monkeypatch.setattr(skillshare.Confirm, "ask", lambda *a, **k: True)
    r = skillshare.install_skill(zp)
    assert r["ok"] is False


def test_run_skill_sandboxed(packed, isolated, monkeypatch):
    zp, manifest = packed
    monkeypatch.setattr(skillshare.Confirm, "ask", lambda *a, **k: True)
    skillshare.install_skill(zp)
    r = skillshare.run_skill("demo")
    assert r["ok"] is True
    assert r["backend"] in ("bwrap", "subprocess")


def test_run_skill_entry_escape_refused(isolated, tmp_path, monkeypatch):
    d = isolated / "skills" / "evil"
    d.mkdir(parents=True)
    (d / "skill.json").write_text(json.dumps(
        {"name": "evil", "version": "1", "description": "x", "entry": "../escape.sh"}))
    r = skillshare.run_skill("evil")
    assert r["ok"] is False and "escapes" in r["error"]


def test_handle_skill_offer_hash_mismatch(monkeypatch):
    manifest = {"name": "demo", "pack_sha256": "0" * 64}
    status, _, _ = skillshare.handle_skill_offer(
        "127.0.0.1", {"manifest": manifest,
                      "pack_b64": base64.b64encode(b"data").decode()})
    assert status == 400


def test_handle_skill_offer_quarantine_and_decline(packed, isolated, monkeypatch):
    zp, manifest = packed
    data = open(zp, "rb").read()
    monkeypatch.setattr(skillshare.Confirm, "ask", lambda *a, **k: False)
    status, _, body = skillshare.handle_skill_offer(
        "127.0.0.1", {"manifest": manifest,
                      "pack_b64": base64.b64encode(data).decode()})
    assert status == 403  # declined -> deleted, never installed
    assert list((isolated / "skills" / "incoming").glob("*.zip")) == []
    assert not (isolated / "skills" / "demo").exists()
