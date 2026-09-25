"""Pins the security property: startup health-check repairs never execute
without explicit user approval, and the exact commands are disclosed first.
"""
import pytest

import core.health as health_mod
import core.repair as repair_mod


@pytest.fixture()
def unhealthy(monkeypatch):
    results = [
        {"name": "jarvis-dev", "status": "ERROR", "error": "boom"},
        {"name": "wikiproxy", "status": "ONLINE", "error": None},
    ]
    monkeypatch.setattr(health_mod, "check_system_health", lambda: results)
    monkeypatch.setattr(health_mod, "display_health_report", lambda r: True)
    return results


@pytest.fixture()
def repair_spy(monkeypatch):
    calls = []
    monkeypatch.setattr(health_mod, "auto_repair_workspace", lambda r: calls.append(r))
    return calls


def test_repairs_require_explicit_yes(unhealthy, repair_spy, monkeypatch):
    monkeypatch.setattr(repair_mod, "load_config", lambda: {"self_repair": True})
    monkeypatch.setattr(repair_mod.Confirm, "ask", lambda *a, **k: False)
    repair_mod.auto_check_on_launch()
    assert repair_spy == [], "repair ran without approval!"


def test_yes_runs_repairs(unhealthy, repair_spy, monkeypatch):
    monkeypatch.setattr(repair_mod, "load_config", lambda: {"self_repair": True})
    monkeypatch.setattr(repair_mod.Confirm, "ask", lambda *a, **k: True)
    repair_mod.auto_check_on_launch()
    assert len(repair_spy) == 1


def test_self_repair_disabled_never_proposes(unhealthy, repair_spy, monkeypatch):
    monkeypatch.setattr(repair_mod, "load_config", lambda: {"self_repair": False})
    asked = []
    monkeypatch.setattr(repair_mod.Confirm, "ask", lambda *a, **k: asked.append(True) or False)
    repair_mod.auto_check_on_launch()
    assert repair_spy == []
    assert asked == [], "should not even prompt when self_repair is disabled"


def test_proposed_commands_are_disclosed(unhealthy, repair_spy, monkeypatch, capsys):
    monkeypatch.setattr(repair_mod, "load_config", lambda: {"self_repair": True})
    monkeypatch.setattr(repair_mod.Confirm, "ask", lambda *a, **k: False)
    repair_mod.auto_check_on_launch()
    out = " ".join(capsys.readouterr().out.split())
    assert "pip install" in out, "repair command not disclosed before prompt"
