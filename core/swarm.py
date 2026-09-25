"""Agent swarm: fan a task out to parallel local workers.

Pipeline: planner breaks the task into independent subtasks → workers
execute them in parallel (bounded) → reviewer synthesizes one result.

- Planner and reviewer are LLM calls via ``core.brain.think_structured``.
- Workers are either "think" (LLM subtask) or "code" (shell/python run
  inside the ``tools/sandbox.py`` Linux sandbox — the swarm never weakens
  sandbox isolation; on non-Linux the code worker reports unavailable
  instead of running unsandboxed).
- Bounded parallelism (default 4 workers), per-worker timeouts, and a
  live progress display. Everything runs locally; no new infrastructure.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

console = Console()

DEFAULT_MAX_WORKERS = 4
DEFAULT_WORKER_TIMEOUT = 180.0
DEFAULT_MAX_SUBTASKS = 6


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

_PLANNER_INSTRUCTIONS = """\
Break the task below into independent subtasks that can run in parallel.
Return STRICT JSON only — no markdown fences, no commentary:

{{"subtasks": [
  {{"id": 1, "title": "short title", "detail": "what to do, self-contained", "kind": "think"}},
  {{"id": 2, "title": "short title", "detail": "exact shell/python code to run", "kind": "code"}}
]}}

Rules:
- "kind" is "think" for research/reasoning/writing, "code" ONLY when the
  subtask is literally running a shell command or python snippet in a
  disposable Linux sandbox (no network, fresh temp dir).
- At most {max_subtasks} subtasks. Keep each detail self-contained.
- If the task cannot be split, return exactly one subtask.

TASK: {task}"""


def _extract_json(text: str) -> Dict:
    """Pull the first {...} JSON object out of model output, defensively."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])


def plan_subtasks(task: str, max_subtasks: int = DEFAULT_MAX_SUBTASKS) -> List[Dict]:
    """Ask the planner LLM for a subtask list; fall back to one subtask."""
    from core.brain import think_structured
    try:
        res = think_structured(
            "Swarm Planner",
            _PLANNER_INSTRUCTIONS.format(max_subtasks=max_subtasks, task=task),
        )
        data = _extract_json(res.get("text", ""))
        raw = data.get("subtasks", [])
        subtasks = []
        for i, s in enumerate(raw[:max_subtasks]):
            if not isinstance(s, dict):
                continue
            kind = s.get("kind", "think")
            subtasks.append({
                "id": s.get("id", i + 1),
                "title": str(s.get("title", f"subtask {i + 1}"))[:120],
                "detail": str(s.get("detail", ""))[:4000],
                "kind": "code" if kind == "code" else "think",
            })
        if subtasks:
            return subtasks
    except Exception:
        pass
    return [{"id": 1, "title": task[:80], "detail": task, "kind": "think"}]


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

def _extract_code(detail: str) -> str:
    """Pull a fenced code block out of the detail, or use the detail as-is."""
    m = re.search(r"```(?:bash|sh|shell|python|py)?\n(.*?)```", detail, re.S)
    if m:
        return m.group(1).strip()
    return detail.strip()


def run_worker(subtask: Dict, timeout: float = DEFAULT_WORKER_TIMEOUT) -> Dict:
    """Execute one subtask. Never raises — failures become status dicts."""
    title = subtask.get("title", "?")
    kind = subtask.get("kind", "think")
    detail = subtask.get("detail", "")
    start = time.time()
    try:
        if kind == "code":
            from tools.sandbox import run_sandboxed
            code = _extract_code(detail)
            if not code:
                return _worker_result(subtask, False, "empty code block", start)
            r = run_sandboxed(code, timeout=min(timeout, 300))
            d = r.to_dict()
            text = (d.get("stdout") or "").strip()
            if d.get("stderr"):
                text += f"\n[stderr]\n{d['stderr'].strip()}"
            if not r.ok:
                return _worker_result(
                    subtask, False,
                    f"sandbox exit={d.get('return_code')} timed_out={d.get('timed_out')} "
                    f"backend={d.get('backend')}{(' error=' + d['error']) if d.get('error') else ''}\n{text}",
                    start, backend=d.get("backend"))
            return _worker_result(subtask, True, text or "(no output)", start,
                                  backend=d.get("backend"))
        else:
            from core.brain import think_structured
            res = think_structured(f"Swarm Worker: {title}", detail)
            text = (res.get("text") or "").strip()
            if not res.get("ok") or not text:
                return _worker_result(subtask, False,
                                      res.get("error") or "empty response", start)
            return _worker_result(subtask, True, text, start)
    except Exception as e:
        return _worker_result(subtask, False, f"{type(e).__name__}: {e}", start)


def _worker_result(subtask: Dict, ok: bool, text: str, start: float,
                   backend: str = "") -> Dict:
    return {
        "id": subtask.get("id"),
        "title": subtask.get("title"),
        "kind": subtask.get("kind"),
        "ok": ok,
        "text": text,
        "backend": backend,
        "elapsed_s": round(time.time() - start, 1),
    }


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------

def review_results(task: str, results: List[Dict]) -> Dict:
    """Synthesize worker outputs into one final answer."""
    from core.brain import think_structured
    ok_results = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    sections = "\n\n".join(
        f"--- subtask {r['id']}: {r['title']} ({r['kind']}) ---\n{r['text']}"
        for r in ok_results
    )
    prompt = (
        "You are the Swarm Reviewer. Workers executed subtasks of the task "
        f"below in parallel. Synthesize their outputs into ONE final answer.\n\n"
        f"ORIGINAL TASK: {task}\n\n{sections}\n\n"
        + (f"\n{len(failed)} subtask(s) failed and were omitted: "
           + ", ".join(f"#{r['id']} {r['title']}" for r in failed) + "\n\n"
           if failed else "\n")
        + "Write the final answer directly — no preamble."
    )
    try:
        res = think_structured("Swarm Reviewer", prompt)
        text = (res.get("text") or "").strip()
        if res.get("ok") and text:
            return {"ok": True, "text": text, "method": "synthesized"}
    except Exception:
        pass
    return {"ok": True, "text": sections or "No worker produced output.",
            "method": "concatenated"}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_swarm(task: str, max_workers: int = DEFAULT_MAX_WORKERS,
              worker_timeout: float = DEFAULT_WORKER_TIMEOUT,
              max_subtasks: int = DEFAULT_MAX_SUBTASKS,
              show_progress: bool = True) -> Dict:
    """Plan → parallel workers → review. Returns a rich result dict."""
    task = task.strip()
    if not task:
        return {"ok": False, "error": "empty task"}
    max_workers = max(1, min(int(max_workers), 8))

    console.print("[bold cyan]🐝 Swarm planner breaking down the task…[/bold cyan]")
    subtasks = plan_subtasks(task, max_subtasks=max_subtasks)
    console.print(f"[dim]{len(subtasks)} subtask(s), up to {max_workers} parallel workers[/dim]")

    results: List[Dict] = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  BarColumn(), transient=not show_progress) as progress:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {}
            for s in subtasks:
                desc = f"worker #{s['id']}: {s['title'][:50]}"
                task_id = progress.add_task(desc, total=1)
                futs[ex.submit(run_worker, s, worker_timeout)] = (s, task_id)
            for fut in as_completed(futs):
                s, task_id = futs[fut]
                try:
                    r = fut.result(timeout=worker_timeout + 30)
                except Exception as e:
                    r = _worker_result(s, False, f"worker crashed: {e}", time.time())
                results.append(r)
                progress.update(task_id, completed=1,
                                description=f"{'✅' if r['ok'] else '❌'} #{s['id']}: {s['title'][:50]}")

    results.sort(key=lambda r: r.get("id") or 0)
    console.print("[bold cyan]🐝 Reviewer synthesizing…[/bold cyan]")
    review = review_results(task, results)
    return {"ok": True, "text": review["text"], "method": review["method"],
            "subtasks": results}


def display_swarm_result(res: Dict) -> None:
    if not res.get("ok"):
        from core.ui import ui_error
        console.print(ui_error("Swarm failed", res.get("error", "unknown"),
                               next_steps="Try a simpler task or check /connections."))
        return
    console.print(Panel(res["text"], title="[bold cyan]🐝 Swarm result[/bold cyan]",
                        border_style="cyan"))
    table = Table(show_header=True, header_style="bold dim", box=None)
    table.add_column("#"); table.add_column("Subtask"); table.add_column("Kind")
    table.add_column("Status"); table.add_column("Time")
    for r in res.get("subtasks", []):
        status = "[green]✓[/green]" if r.get("ok") else "[red]✗[/red]"
        table.add_row(str(r.get("id")), (r.get("title") or "")[:40],
                      r.get("kind") or "?", status, f"{r.get('elapsed_s', '?')}s")
    console.print(table)
