"""Round C: Sims — lifecycle, portability, tool gating, chat."""
import json

import pytest

import core.config as config_mod


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    import core.sims as sims_mod
    monkeypatch.setattr(sims_mod, "SIMS_DIR", tmp_path / "sims")
    monkeypatch.setattr(sims_mod, "console",
                        __import__("rich.console", fromlist=["Console"]).Console(file=open("/dev/null", "w")))
    return tmp_path


def test_create_and_list(isolated):
    from core.sims import create_sim, list_sims
    res = create_sim("Helper", avatar="🧪", personality="mentor",
                     system_prompt="You help.", allowed_tools=["shell"],
                     model="llama3")
    assert res["ok"]
    sims = list_sims()
    assert any(s["name"] == "Helper" for s in sims)
    assert not create_sim("Helper")["ok"]  # duplicate
    assert not create_sim("bad name!")["ok"]


def test_forbidden_tools_stripped(isolated):
    from core.sims import create_sim, load_sim, sim_may_use_tool
    create_sim("Sneaky", system_prompt="x",
               allowed_tools=["shell", "p2p_send_file", "keyring_write"])
    sim = load_sim("Sneaky")
    assert "p2p_send_file" not in sim["allowed_tools"]
    assert "keyring_write" not in sim["allowed_tools"]
    assert not sim_may_use_tool(sim, "p2p_send_file")
    assert sim_may_use_tool(sim, "shell")
    assert not sim_may_use_tool(sim, "browser")  # not allowlisted


def test_export_import_roundtrip(isolated, tmp_path):
    from core.sims import create_sim, export_sim, import_sim, load_sim, delete_sim
    create_sim("Travel", avatar="✈️", system_prompt="You plan trips.",
               allowed_tools=[], model="m1", description="Trip planner")
    dest = tmp_path / "travel.sim.json"
    assert export_sim("Travel", str(dest))["ok"]
    assert dest.exists()
    delete_sim("Travel", _confirmed=True)
    res = import_sim(str(dest))
    assert res["ok"] and res["name"] == "Travel"
    sim = load_sim("Travel")
    assert sim["avatar"] == "✈️" and sim["system_prompt"] == "You plan trips."


def test_import_rejects_bad_docs(isolated, tmp_path):
    from core.sims import import_sim
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "NoPrompt"}))  # missing system_prompt
    assert not import_sim(str(bad))["ok"]
    notjson = tmp_path / "not.json"
    notjson.write_text("{nope")
    assert not import_sim(str(notjson))["ok"]
    assert not import_sim(str(tmp_path / "missing.json"))["ok"]


def test_sim_chat_uses_brain(isolated, monkeypatch):
    from core.sims import create_sim, sim_chat
    calls = {}

    def fake_think(context, task, model=None):
        calls["context"] = context
        calls["task"] = task
        calls["model"] = model
        return "sim reply"

    import core.brain as brain_mod
    monkeypatch.setattr(brain_mod, "think", fake_think)
    create_sim("Helper", system_prompt="Be helpful.", model="mX")
    res = sim_chat("Helper", "hi", [{"role": "user", "text": "yo"}])
    assert res["ok"] and res["reply"] == "sim reply"
    assert "Be helpful." in calls["context"]
    assert calls["task"] == "hi"
    assert calls["model"] == "mX"
    assert not sim_chat("Ghost", "hi")["ok"]


def test_delete_sim(isolated, monkeypatch):
    from core.sims import create_sim, delete_sim, list_sims
    monkeypatch.setattr("core.approvals.confirm", lambda *a, **k: True)
    create_sim("Temp", system_prompt="x")
    assert delete_sim("Temp")["ok"]
    assert "Temp" not in [s["name"] for s in list_sims()]
    assert not delete_sim("Ghost")["ok"]
