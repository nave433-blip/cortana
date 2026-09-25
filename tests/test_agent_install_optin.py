"""Tests for the opt-in agent install redesign.

Pins the security property: nothing is ever installed without explicit
per-item user approval, "never" choices persist, and non-interactive
callers get detection-only behavior.
"""
import pytest

import core.agent_manager as am


@pytest.fixture()
def no_binaries(monkeypatch):
    """Pretend no agent CLI is installed."""
    monkeypatch.setattr(am.shutil, "which", lambda binary: None)


def test_check_agents_is_pure_detection(no_binaries):
    statuses = am.check_agents()
    assert len(statuses) == len(am.AGENT_REGISTRY)
    assert all(s["installed"] is False for s in statuses)
    assert all(s["install"] and s["check"] for s in statuses)


def test_check_agents_detects_present(monkeypatch):
    monkeypatch.setattr(am.shutil, "which", lambda binary: "/usr/bin/" + binary)
    assert all(s["installed"] for s in am.check_agents())


def test_decline_all_installs_nothing(no_binaries):
    calls = []
    report = am.prompt_and_install_agents(
        prompter=lambda prompt: "n",
        runner=lambda cmd: calls.append(cmd),
    )
    assert calls == [], "install ran without approval!"
    assert len(report["skipped"]) == len(am.AGENT_REGISTRY)
    assert report["installed"] == []


def test_approve_installs_only_approved(no_binaries):
    calls = []
    answers = iter(["y"] + ["n"] * (len(am.AGENT_REGISTRY) - 1))
    report = am.prompt_and_install_agents(
        prompter=lambda prompt: next(answers),
        runner=lambda cmd: calls.append(cmd),
    )
    assert len(calls) == 1
    assert len(report["installed"]) == 1
    assert calls[0] == am.AGENT_REGISTRY[report["installed"][0]]["install"]


def test_never_persists_and_skips_next_time(no_binaries):
    saved = {}
    config = {}

    def fake_save(cfg):
        saved.update(cfg)

    answers = iter(["never"] + ["n"] * (len(am.AGENT_REGISTRY) - 1))
    report = am.prompt_and_install_agents(
        config=config,
        save_config_fn=fake_save,
        prompter=lambda prompt: next(answers),
        runner=lambda cmd: (_ for _ in ()).throw(AssertionError("no installs!")),
    )
    first = report["declined"][0]
    assert saved.get(am.DECLINED_CONFIG_KEY) == [first]

    # Second run: declined agent is skipped without any prompt.
    prompts = []
    report2 = am.prompt_and_install_agents(
        config=dict(saved),
        save_config_fn=fake_save,
        prompter=lambda prompt: prompts.append(prompt) or "n",
        runner=lambda cmd: (_ for _ in ()).throw(AssertionError("no installs!")),
    )
    assert report2["already_declined"] == [first]
    assert len(prompts) == len(am.AGENT_REGISTRY) - 1


def test_install_unknown_agent_fails_cleanly():
    assert am.install_agent("NoSuchAgent") is False


def test_install_failure_reported_not_raised(no_binaries):
    def boom(cmd):
        raise RuntimeError("nope")

    assert am.install_agent("Codex", runner=boom) is False


def test_auto_install_api_removed():
    """The old silent auto-installer must not exist anymore."""
    assert not hasattr(am, "check_and_install_agents")


def test_startup_does_not_call_auto_installer():
    import inspect
    import core.startup as startup_mod

    src = inspect.getsource(startup_mod.startup_check_and_login)
    assert "check_and_install_agents" not in src
    assert "prompt_and_install_agents" in src
