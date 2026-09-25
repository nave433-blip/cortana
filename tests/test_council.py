"""Track 1 tests: council mode deliberation.

No network, no LLMs — ask_fn and synthesize_fn are injected stubs, and
member resolution is monkeypatched.
"""
import pytest

import core.council as council


# ---------------------------------------------------------------- helpers

def make_stub():
    """ask_fn stub: canned proposals + canned critiques, records prompts."""
    prompts = []  # (kind, provider, prompt)

    def ask_fn(provider, model, prompt, timeout):
        if prompt.startswith("Critique these"):
            prompts.append(("critique", provider, prompt))
            return {"provider": provider, "model": model, "ok": True,
                    "text": f"CRITIQUE-{provider}: first point is right, "
                            f"second point is missing evidence.", "latency_ms": 1}
        prompts.append(("propose", provider, prompt))
        n = sum(1 for k, p, _ in prompts if k == "propose" and p == provider)
        return {"provider": provider, "model": model, "ok": True,
                "text": f"ANSWER-{provider}-v{n}", "latency_ms": 1}

    return ask_fn, prompts


def make_synth():
    seen = {}

    def synthesize_fn(question, answers):
        seen["question"] = question
        seen["answers"] = list(answers)
        return {"ok": True, "text": "FINAL-ANSWER", "method": "test-synth"}

    return synthesize_fn, seen


MEMBERS = [{"provider": "p1", "model": "m1"},
           {"provider": "p2", "model": "m2"}]


# ---------------------------------------------------------------- estimate

def test_estimate_calls_math():
    assert council.estimate_calls(3, 3) == 3 * 3 + 3 * 2 + 1 == 16
    assert council.estimate_calls(2, 1) == 2 + 0 + 1 == 3
    assert council.estimate_calls(1, 2) == 2 + 1 + 1 == 4
    assert council.estimate_calls(0, 3) == 1  # still tries synthesis shape


# ---------------------------------------------------------------- deliberation flow

def test_rounds_bounded_calls_made_matches_estimate():
    ask_fn, _ = make_stub()
    synth, _ = make_synth()
    res = council.council_ask("What is 2+2?", rounds=3, members=MEMBERS,
                              ask_fn=ask_fn, synthesize_fn=synth)
    assert res["ok"] is True
    assert res["calls_made"] == council.estimate_calls(2, 3) == 11
    assert len(res["rounds"]) == 3
    # last round has no critique phase
    assert res["rounds"][-1]["critiques"] == []
    assert len(res["rounds"][0]["critiques"]) == 2
    assert res["members"] == MEMBERS


def test_round1_critique_text_appears_in_round2_prompts():
    ask_fn, prompts = make_stub()
    synth, _ = make_synth()
    council.council_ask("Why is the sky blue?", rounds=2, members=MEMBERS,
                        ask_fn=ask_fn, synthesize_fn=synth)
    round2_prompts = [p for k, prov, p in prompts if k == "propose"][2:]
    assert len(round2_prompts) == 2
    for prompt in round2_prompts:
        # exact phrase from the spec'd revision prompt
        assert "Here are critiques of the previous proposals:" in prompt
        assert "Revise and improve your answer" in prompt
        # critique text from round 1 shows up in round 2 prompts
        assert "CRITIQUE-p1:" in prompt
        assert "CRITIQUE-p2:" in prompt
        # member's own previous proposal is included
        assert "ANSWER-" in prompt and "Your own previous answer" in prompt


def test_final_synthesis_receives_final_proposals():
    ask_fn, _ = make_stub()
    synth, seen = make_synth()
    res = council.council_ask("Q?", rounds=2, members=MEMBERS,
                              ask_fn=ask_fn, synthesize_fn=synth)
    assert res["final"] == "FINAL-ANSWER"
    assert res["method"] == "test-synth"
    assert seen["question"] == "Q?"
    final_texts = {a["text"] for a in seen["answers"]}
    # v2 answers are the round-2 revisions
    assert final_texts == {"ANSWER-p1-v2", "ANSWER-p2-v2"}
    assert len(seen["answers"]) == 2


def test_attributions_cover_every_ask_and_every_member():
    ask_fn, _ = make_stub()
    synth, _ = make_synth()
    res = council.council_ask("Q?", rounds=3, members=MEMBERS,
                              ask_fn=ask_fn, synthesize_fn=synth)
    assert len(res["attributions"]) == res["calls_made"] - 1  # minus synthesis
    providers = {a["provider"] for a in res["attributions"]}
    assert providers == {"p1", "p2"}
    # both proposals and critiques recorded per member
    for prov in ("p1", "p2"):
        mine = [a for a in res["attributions"] if a["provider"] == prov]
        assert len(mine) == 3 + 2  # 3 proposals + 2 critiques


def test_failed_proposals_are_honest_not_faked():
    def flaky(provider, model, prompt, timeout):
        if provider == "p2":
            return {"provider": provider, "model": model, "ok": False,
                    "error": "boom", "latency_ms": 5}
        return {"provider": provider, "model": model, "ok": True,
                "text": "p1 answer", "latency_ms": 1}

    synth, seen = make_synth()
    res = council.council_ask("Q?", rounds=2, members=MEMBERS,
                              ask_fn=flaky, synthesize_fn=synth)
    assert res["ok"] is True  # p1 carries the round
    assert {a["text"] for a in seen["answers"]} == {"p1 answer"}
    failed = [a for a in res["attributions"] if not a["ok"]]
    assert failed and all(a["error"] == "boom" for a in failed)


def test_all_proposals_failed_returns_honest_error():
    def dead(provider, model, prompt, timeout):
        return {"provider": provider, "model": model, "ok": False,
                "error": "down", "latency_ms": 1}

    res = council.council_ask("Q?", rounds=2, members=MEMBERS,
                              ask_fn=dead, synthesize_fn=lambda q, a: {"text": "x"})
    assert res["ok"] is False
    assert "failed" in res["error"]
    assert res["next_steps"]


def test_synthesize_failure_falls_back_to_attributed_concat():
    ask_fn, _ = make_stub()

    def bad_synth(question, answers):
        raise RuntimeError("synth exploded")

    res = council.council_ask("Q?", rounds=1, members=MEMBERS,
                              ask_fn=ask_fn, synthesize_fn=bad_synth)
    assert res["ok"] is True
    assert res["method"] == "concatenated"
    assert "ANSWER-p1-v1" in res["final"]
    assert "ANSWER-p2-v1" in res["final"]


def test_empty_question_is_honest_error():
    ask_fn, _ = make_stub()
    res = council.council_ask("   ", members=MEMBERS, ask_fn=ask_fn)
    assert res["ok"] is False
    assert res["error"] == "empty question"


def test_empty_members_error_shape():
    res = council.council_ask("Q?", members=[])
    assert res["ok"] is False
    assert res["error"] == "no council members available"
    assert "next_steps" in res
    assert "/connect" in res["next_steps"]


def test_members_none_with_no_providers_errors(monkeypatch):
    monkeypatch.setattr(council, "hive_candidates", lambda providers=None: [])
    res = council.council_ask("Q?", members=None, ask_fn=lambda *a: {})
    assert res["ok"] is False
    assert res["error"] == "no council members available"


# ---------------------------------------------------------------- member resolution

def test_custom_config_string_and_dict_forms(monkeypatch):
    monkeypatch.setattr(council, "resolve_hive_model",
                        lambda p: {"openai": "openai/gpt-x", "groq": "groq/llama-x"}.get(p))
    cfg = {"council_members": ["openai", "anthropic:custom-model",
                               {"provider": "groq"}, {"provider": "nope"},
                               "openai:", "", 123]}
    members = council.get_council_members(cfg)
    assert members == [
        {"provider": "openai", "model": "openai/gpt-x"},
        {"provider": "anthropic", "model": "custom-model"},
        {"provider": "groq", "model": "groq/llama-x"},
    ]


def test_default_members_come_from_hive_candidates(monkeypatch):
    def fake_candidates(providers=None):
        return [{"provider": f"p{i}", "model": f"m{i}"} for i in range(1, 6)] + [
            {"provider": "skipme", "skipped": True, "reason": "x"}]
    monkeypatch.setattr(council, "hive_candidates", fake_candidates)
    members = council.get_council_members({})
    assert members == [{"provider": f"p{i}", "model": f"m{i}"} for i in range(1, 4)]


def test_default_members_skip_unusable(monkeypatch):
    def fake_candidates(providers=None):
        return [{"provider": "bad", "skipped": True, "reason": "no model"},
                {"provider": "good", "model": "gm"}]
    monkeypatch.setattr(council, "hive_candidates", fake_candidates)
    assert council.get_council_members({}) == [{"provider": "good", "model": "gm"}]


# ---------------------------------------------------------------- command handler

def test_handle_council_command_parses_flags(monkeypatch, capsys):
    seen = {}

    def fake_ask(question, rounds=3, members=None, timeout=90.0,
                 ask_fn=None, synthesize_fn=None):
        seen["question"] = question
        seen["rounds"] = rounds
        seen["members"] = members
        return {"ok": True, "final": "done", "method": "test",
                "rounds": [], "attributions": [],
                "calls_made": 1, "members": members or []}

    monkeypatch.setattr(council, "council_ask", fake_ask)
    monkeypatch.setattr(council, "is_auto_approve", lambda: True)
    monkeypatch.setattr(council, "get_council_members",
                        lambda cfg=None: [{"provider": p, "model": "m"}
                                          for p in (cfg or {}).get("council_members") or ["a", "b"]])
    # suppress rich rendering of the fake result
    monkeypatch.setattr(council, "display_council_result", lambda res: None)

    council.handle_council_command("--rounds 2 --members x,y what is up")
    assert seen["question"] == "what is up"
    assert seen["rounds"] == 2
    assert [m["provider"] for m in seen["members"]] == ["x", "y"]
    out = capsys.readouterr().out
    assert "Council mode will make ~7 model calls across 2 providers and 2 rounds." in out


def test_handle_council_command_cost_warning_shown_before_confirm(monkeypatch, capsys):
    order = []

    def fake_confirm(prompt, default=False, **kwargs):
        order.append(("confirm", capsys.readouterr().out))
        return True

    monkeypatch.setattr(council, "confirm", fake_confirm)
    monkeypatch.setattr(council, "is_auto_approve", lambda: False)
    monkeypatch.setattr(council, "get_council_members",
                        lambda cfg=None: [{"provider": "a", "model": "m"}])
    monkeypatch.setattr(council, "council_ask",
                        lambda *a, **k: {"ok": True, "final": "x", "method": "t",
                                         "rounds": [], "attributions": [],
                                         "calls_made": 1, "members": []})
    monkeypatch.setattr(council, "display_council_result", lambda res: None)

    council.handle_council_command("hello there")
    kind, captured = order[0]
    assert kind == "confirm"
    assert "Council mode will make ~" in captured


def test_handle_council_command_no_members_shows_error(monkeypatch, capsys):
    shown = {}
    monkeypatch.setattr(council, "get_council_members", lambda cfg=None: [])
    monkeypatch.setattr(council, "display_council_result", lambda res: shown.update(res))
    council.handle_council_command("some question")
    assert shown.get("ok") is False
    assert shown.get("error") == "no council members available"
