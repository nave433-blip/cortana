"""Mocked end-to-end coverage for the flows users actually hit.

No network calls: keyring access, provider validation, LLM backends and
interactive prompts are all mocked. What IS exercised is the real wiring:
wizard dispatch -> prompts -> validation -> secure storage, REPL command
routing, `connections --test` reachability plumbing, and the nave agent
loop's happy path.
"""
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, "/home/hatch/workspace/jarvis-dev")

import core.connect as connect_mod
from core.auth import AuthManager
from core.handler import CommandHandler


def _key_provider_name():
    for name, info in AuthManager.PROVIDERS.items():
        if not info.get("host_only"):
            return name, info
    raise AssertionError("no key-based provider found")


# ---------------------------------------------------------------------------
# /connect wizard
# ---------------------------------------------------------------------------

class TestConnectWizard:
    def test_wizard_back_exits_cleanly(self):
        """Choosing 'b' lists providers then returns without side effects."""
        with patch.object(connect_mod.Prompt, "ask", return_value="b"), \
             patch.object(connect_mod, "get_key_secure", return_value=None), \
             patch.object(connect_mod, "get_provider_host", return_value=None):
            assert connect_mod.run_connect_wizard() is None

    def test_wizard_key_flow_validates_before_saving(self):
        """Happy path: pick provider -> paste key -> validate ok -> saved."""
        name, info = _key_provider_name()
        idx = list(AuthManager.PROVIDERS).index(name) + 1  # 1-based menu
        saved = {}

        def fake_save(provider, key):
            saved["provider"] = provider
            saved["key"] = key
            return {"stored_in": "keyring"}

        with patch.object(connect_mod.Prompt, "ask", return_value=str(idx)), \
             patch.object(connect_mod.Confirm, "ask", return_value=False), \
             patch("core.connect.getpass.getpass", return_value="sk-test-123"), \
             patch.object(connect_mod, "validate_provider_connection",
                          return_value={"ok": True}) as v, \
             patch.object(connect_mod, "save_key_secure", side_effect=fake_save):
            connect_mod.run_connect_wizard()

        v.assert_called_once()
        assert v.call_args[0][0] == name
        assert v.call_args[1]["extra"] == {"key": "sk-test-123"}
        # validation happened, then the SAME key was stored
        assert saved == {"provider": name, "key": "sk-test-123"}

    def test_wizard_failed_validation_never_saves(self):
        """A rejected key must never reach secure storage."""
        name, _ = _key_provider_name()
        idx = list(AuthManager.PROVIDERS).index(name) + 1
        with patch.object(connect_mod.Prompt, "ask", return_value=str(idx)), \
             patch.object(connect_mod.Confirm, "ask", return_value=False), \
             patch("core.connect.getpass.getpass", return_value="sk-bad"), \
             patch.object(connect_mod, "validate_provider_connection",
                          return_value={"ok": False, "error": "bad key"}), \
             patch.object(connect_mod, "save_key_secure") as save:
            connect_mod.run_connect_wizard()
        save.assert_not_called()

    def test_connect_provider_cli_key_never_echoed(self, capsys):
        """connect-provider --key path: key validated, saved, never printed."""
        name, _ = _key_provider_name()
        with patch.object(connect_mod, "validate_provider_connection",
                          return_value={"ok": True}), \
             patch.object(connect_mod, "save_key_secure",
                          return_value={"stored_in": "keyring"}) as save:
            connect_mod.connect_provider_cli(name, key="sk-super-secret-xyz")
        save.assert_called_once_with(name, "sk-super-secret-xyz")
        out = capsys.readouterr().out
        assert "sk-super-secret-xyz" not in out

    def test_connect_provider_cli_unknown_provider(self, capsys):
        connect_mod.connect_provider_cli("no-such-provider", key="x")
        assert "Unknown provider" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# REPL routing (registry-level, no LLM)
# ---------------------------------------------------------------------------

class TestReplRouting:
    def _handler(self):
        h = CommandHandler()
        for cmd in ["/connect", "/connections", "/help", "/t", "/menu"]:
            h.register(cmd, lambda x: None)
        return h

    def test_connect_routes_internal(self):
        res = self._handler().handle("/connect")
        assert res["type"] == "internal" and res["command"] == "/connect"

    def test_connections_routes_internal(self):
        res = self._handler().handle("/connections")
        assert res["type"] == "internal" and res["command"] == "/connections"

    def test_help_routes_internal(self):
        """/help must hit the registry (it was missing -> fell into chat)."""
        res = self._handler().handle("/help")
        assert res["type"] == "internal" and res["command"] == "/help"

    def test_t_alias_routes_internal(self):
        res = self._handler().handle("/t")
        assert res["type"] == "internal" and res["command"] == "/t"

    def test_plain_help_word_routes_without_slash(self):
        """/help registered => 'help' is a no-slash plain command too."""
        h = self._handler()
        tokens = h._tokenize("help")
        matched, _ = h._match_known(tokens)
        assert matched == "/help"


# ---------------------------------------------------------------------------
# connections --test plumbing
# ---------------------------------------------------------------------------

class TestConnectionsCommand:
    def test_test_flag_reaches_connection_status(self):
        import cli
        rows = [{"provider": "openai", "display": "OpenAI", "configured": True,
                 "reachable": True, "attention": "", "reason": ""}]
        with patch("core.connect.connection_status",
                   return_value=rows) as cs:
            cli.connections(test=True)
        cs.assert_called_once_with(test=True)

    def test_no_test_flag_by_default(self):
        import cli
        with patch("core.connect.connection_status",
                   return_value=[]) as cs:
            cli.connections(test=False)
        cs.assert_called_once_with(test=False)


# ---------------------------------------------------------------------------
# nave_loop happy path with a fake LLM backend
# ---------------------------------------------------------------------------

class TestNaveLoop:
    def test_happy_path(self):
        import core.nave_loop as nl
        agent = SimpleNamespace(role="Coder", name="coder",
                                instruction="write code")
        fake_call = {"ok": True, "agent": agent, "model": "fake",
                     "output": "print('hi')", "thinking": "trivial"}
        integrator = {"ok": True,
                      "text": json.dumps({"final_answer": "done",
                                          "reasoning_summary": "s",
                                          "confidence": "high"})}
        with patch.object(nl, "get_task_aware_agents", return_value=[agent]), \
             patch.object(nl, "_run_agent_call", return_value=fake_call), \
             patch.object(nl, "think_structured", return_value=integrator):
            res = nl.run_nave_loop("do the thing", cycles=1)
        assert res["ok"] is True
        assert res["final_answer"] == "done"
        assert len(res["history"]) == 1

    def test_all_agents_fail_reports_cleanly(self):
        import core.nave_loop as nl
        agent = SimpleNamespace(role="Coder", name="coder",
                                instruction="write code")
        with patch.object(nl, "get_task_aware_agents", return_value=[agent]), \
             patch.object(nl, "_run_agent_call",
                          return_value={"ok": False, "error": "down",
                                        "agent": agent}):
            res = nl.run_nave_loop("do the thing", cycles=1)
        assert res["ok"] is False
        assert "history" in res


# ---------------------------------------------------------------------------
# debug_loop contract: think_structured dict, not think() str
# ---------------------------------------------------------------------------

class TestDebugLoopContract:
    def test_debug_loop_proceeds_on_ok_dict(self):
        """Regression: debug_loop used think() (str) and aborted cycle 1."""
        import core.agent as agent_mod
        calls = []

        def fake_think_structured(context, task, model=None, prompt_name=None):
            calls.append(task)
            # first cycle returns no tool calls -> final answer path
            return {"ok": True, "text": "All fixed.", "provider": "fake"}

        with patch.object(agent_mod, "think_structured",
                          side_effect=fake_think_structured):
            agent_mod.debug_loop("some issue")
        assert calls, "think_structured was never called"

    def test_debug_loop_aborts_on_provider_failure(self, capsys):
        import core.agent as agent_mod
        with patch.object(agent_mod, "think_structured",
                          return_value={"ok": False,
                                        "error": "no providers"}):
            agent_mod.debug_loop("some issue")
        assert "Brain Loop Interrupted" in capsys.readouterr().out
