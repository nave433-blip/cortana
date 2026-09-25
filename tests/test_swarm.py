"""Track 2 tests: agent swarm planner/workers/reviewer.

LLM calls and sandbox execution are mocked — no network, no real exec.
"""
import pytest

import core.swarm as swarm


def _think_ok(text):
    def _f(context, task, model=None, prompt_name=None):
        return {"ok": True, "text": text}
    return _f


# ---------------------------------------------------------------- planner

def test_plan_subtasks_parses_json(monkeypatch):
    import core.brain as brain
    payload = ('{"subtasks": ['
               '{"id": 1, "title": "A", "detail": "do A", "kind": "think"},'
               '{"id": 2, "title": "B", "detail": "echo hi", "kind": "code"}]}')
    monkeypatch.setattr(brain, "think_structured", _think_ok(payload))
    subs = swarm.plan_subtasks("some task")
    assert len(subs) == 2
    assert subs[0]["kind"] == "think"
    assert subs[1]["kind"] == "code"


def test_plan_subtasks_fallback_on_llm_failure(monkeypatch):
    import core.brain as brain
    def _raise(*a, **k):
        raise RuntimeError("no llm")
    monkeypatch.setattr(brain, "think_structured", _raise)
    subs = swarm.plan_subtasks("do the thing")
    assert len(subs) == 1
    assert subs[0]["kind"] == "think"
    assert subs[0]["detail"] == "do the thing"


def test_plan_subtasks_caps_count(monkeypatch):
    import core.brain as brain
    payload = '{"subtasks": [' + ",".join(
        f'{{"id": {i}, "title": "t{i}", "detail": "d{i}", "kind": "think"}}'
        for i in range(20)) + ']}'
    monkeypatch.setattr(brain, "think_structured", _think_ok(payload))
    subs = swarm.plan_subtasks("big task", max_subtasks=6)
    assert len(subs) == 6


# ---------------------------------------------------------------- workers

def test_run_worker_think(monkeypatch):
    import core.brain as brain
    monkeypatch.setattr(brain, "think_structured", _think_ok("worker output"))
    r = swarm.run_worker({"id": 1, "title": "T", "detail": "d", "kind": "think"})
    assert r["ok"] is True and r["text"] == "worker output"


def test_run_worker_think_failure(monkeypatch):
    import core.brain as brain
    monkeypatch.setattr(brain, "think_structured",
                        lambda *a, **k: {"ok": False, "error": "bad"})
    r = swarm.run_worker({"id": 1, "title": "T", "detail": "d", "kind": "think"})
    assert r["ok"] is False


def test_run_worker_code_uses_sandbox(monkeypatch):
    from tools.sandbox import SandboxResult
    import tools.sandbox as sandbox_mod
    seen = {}

    def _fake(command, **kwargs):
        seen["command"] = command
        seen["timeout"] = kwargs.get("timeout")
        return SandboxResult(stdout="sandboxed out\n", stderr="",
                             exit_code=0, backend="subprocess")
    monkeypatch.setattr(sandbox_mod, "run_sandboxed", _fake)
    r = swarm.run_worker({"id": 2, "title": "run it", "detail": "```bash\necho hi\n```",
                          "kind": "code"})
    assert r["ok"] is True
    assert "sandboxed out" in r["text"]
    assert seen["command"] == "echo hi"  # fenced block extracted
    assert r["backend"] == "subprocess"


def test_run_worker_code_failure_reported(monkeypatch):
    from tools.sandbox import SandboxResult
    import tools.sandbox as sandbox_mod
    monkeypatch.setattr(
        sandbox_mod, "run_sandboxed",
        lambda command, **kw: SandboxResult(stdout="", stderr="nope",
                                            exit_code=1, backend="subprocess"))
    r = swarm.run_worker({"id": 3, "title": "bad", "detail": "exit 1", "kind": "code"})
    assert r["ok"] is False
    assert "exit=1" in r["text"]


def test_run_worker_code_unavailable_not_faked(monkeypatch):
    from tools.sandbox import SandboxResult
    import tools.sandbox as sandbox_mod
    monkeypatch.setattr(
        sandbox_mod, "run_sandboxed",
        lambda command, **kw: SandboxResult(backend="unavailable",
                                            error="no linux here"))
    r = swarm.run_worker({"id": 4, "title": "x", "detail": "echo hi", "kind": "code"})
    assert r["ok"] is False
    assert "unavailable" in r["text"]


# ---------------------------------------------------------------- reviewer

def test_review_synthesis(monkeypatch):
    import core.brain as brain
    monkeypatch.setattr(brain, "think_structured", _think_ok("FINAL"))
    out = swarm.review_results("task", [
        {"id": 1, "title": "A", "kind": "think", "ok": True, "text": "out A"}])
    assert out == {"ok": True, "text": "FINAL", "method": "synthesized"}


def test_review_fallback_concatenates(monkeypatch):
    import core.brain as brain
    def _raise(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(brain, "think_structured", _raise)
    out = swarm.review_results("task", [
        {"id": 1, "title": "A", "kind": "think", "ok": True, "text": "out A"}])
    assert out["method"] == "concatenated"
    assert "out A" in out["text"]


# ---------------------------------------------------------------- orchestrator

def test_run_swarm_end_to_end(monkeypatch):
    monkeypatch.setattr(swarm, "plan_subtasks", lambda task, max_subtasks=6: [
        {"id": 1, "title": "one", "detail": "d1", "kind": "think"},
        {"id": 2, "title": "two", "detail": "d2", "kind": "think"},
    ])
    calls = []

    def _worker(subtask, timeout=180.0):
        calls.append(subtask["id"])
        return {"id": subtask["id"], "title": subtask["title"],
                "kind": "think", "ok": True, "text": f"res{subtask['id']}",
                "elapsed_s": 0.1}
    monkeypatch.setattr(swarm, "run_worker", _worker)
    monkeypatch.setattr(swarm, "review_results",
                        lambda task, results: {"ok": True, "text": "DONE",
                                              "method": "synthesized"})
    res = swarm.run_swarm("do stuff", max_workers=2, show_progress=False)
    assert res["ok"] is True and res["text"] == "DONE"
    assert sorted(calls) == [1, 2]
    assert len(res["subtasks"]) == 2


def test_run_swarm_empty_task():
    res = swarm.run_swarm("   ", show_progress=False)
    assert res["ok"] is False


def test_run_swarm_worker_timeout_counted(monkeypatch):
    # A worker that raises must not take the whole swarm down.
    monkeypatch.setattr(swarm, "plan_subtasks", lambda task, max_subtasks=6: [
        {"id": 1, "title": "ok", "detail": "d", "kind": "think"},
        {"id": 2, "title": "boom", "detail": "d", "kind": "think"},
    ])

    def _worker(subtask, timeout=180.0):
        if subtask["id"] == 2:
            raise TimeoutError("too slow")
        return {"id": 1, "title": "ok", "kind": "think", "ok": True,
                "text": "fine", "elapsed_s": 0.1}
    monkeypatch.setattr(swarm, "run_worker", _worker)
    monkeypatch.setattr(swarm, "review_results",
                        lambda task, results: {"ok": True, "text": "R",
                                              "method": "concatenated"})
    res = swarm.run_swarm("t", show_progress=False)
    assert res["ok"] is True
    by_id = {r["id"]: r for r in res["subtasks"]}
    assert by_id[1]["ok"] is True and by_id[2]["ok"] is False
