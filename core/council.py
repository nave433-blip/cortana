"""Council mode: multi-round deliberative consensus across AI providers.

Experimental and opt-in — off by default. Unlike the hive (one parallel ask
+ synthesis), the council runs bounded deliberation rounds: every member
proposes an answer, then each member critiques all current proposals in a
single call, then members revise their answers in light of the critiques.
After the final round the last proposals are synthesized into one answer.

Cost: ``estimate_calls(members, rounds)`` = M*R proposals + M*(R-1)
critiques + 1 final synthesis. The user is warned up front.
"""
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from core.approvals import confirm, is_auto_approve
from core.config import load_config
from core.hive import _ask_one, hive_candidates, resolve_hive_model, synthesize_consensus

console = Console()

DEFAULT_ROUNDS = 3
DEFAULT_TIMEOUT = 90.0
DEFAULT_MEMBERS = 3

NO_MEMBERS_ERROR = "no council members available"
NO_MEMBERS_NEXT_STEPS = (
    "Run /connect to link a provider, or set council_members in config."
)


def _no_members_result() -> Dict:
    return {"ok": False, "error": NO_MEMBERS_ERROR,
            "next_steps": NO_MEMBERS_NEXT_STEPS}


# ---------------------------------------------------------------------------
# Member resolution
# ---------------------------------------------------------------------------

def _parse_member_entry(entry: Any) -> Optional[Dict]:
    """One config entry -> {provider, model}, or None when unresolvable.

    Accepts "provider", "provider:model", or {"provider": ..., "model": ...}.
    Models are resolved via resolve_hive_model; entries that can't be
    resolved are dropped (never guessed).
    """
    if isinstance(entry, dict):
        provider = entry.get("provider")
        model = entry.get("model") or (resolve_hive_model(provider) if provider else None)
    elif isinstance(entry, str):
        entry = entry.strip()
        if not entry:
            return None
        if ":" in entry:
            provider, model = entry.split(":", 1)
            provider, model = provider.strip(), model.strip()
        else:
            provider, model = entry, resolve_hive_model(entry)
    else:
        return None
    if not provider or not model:
        return None
    return {"provider": provider, "model": model}


def get_council_members(cfg: Optional[Dict] = None) -> List[Dict]:
    """Resolve the council membership.

    Config key ``council_members`` may be a list of provider names,
    "provider:model" strings, or {"provider", "model"} dicts. When unset,
    defaults to the first DEFAULT_MEMBERS usable entries from
    hive_candidates(). Each item: {"provider", "model"}.
    """
    try:
        cfg = load_config() if cfg is None else cfg
    except Exception:
        cfg = {}
    raw = (cfg or {}).get("council_members")
    if isinstance(raw, list):
        members = []
        for entry in raw:
            parsed = _parse_member_entry(entry)
            if parsed:
                members.append(parsed)
        return members
    usable = [c for c in hive_candidates() if not c.get("skipped")]
    return [{"provider": c["provider"], "model": c["model"]}
            for c in usable[:DEFAULT_MEMBERS]]


def estimate_calls(n_members: int, rounds: int) -> int:
    """M*R proposals + M*(R-1) critiques + 1 final synthesis."""
    n_members = max(0, int(n_members))
    rounds = max(1, int(rounds))
    return n_members * rounds + n_members * (rounds - 1) + 1


# ---------------------------------------------------------------------------
# Deliberation
# ---------------------------------------------------------------------------

def _default_ask_fn(provider: str, model: str, prompt: str, timeout: float) -> Dict:
    """Thin wrapper over hive's single-provider ask. Never raises."""
    return _ask_one(provider, model, prompt, timeout)


def _direct_prompt(question: str) -> str:
    return f"Answer the following question directly:\n\n{question}"


def _revision_prompt(question: str, own_previous: str, critiques: List[Dict]) -> str:
    critique_block = "\n\n".join(
        f"[{c['provider']} ({c['model']})] {c['text']}"
        for c in critiques if c.get("ok") and c.get("text")
    )
    return (
        f"Here are critiques of the previous proposals:\n\n{critique_block}\n\n"
        f"Your own previous answer:\n\n{own_previous}\n\n"
        f"Revise and improve your answer to the question: '{question}'"
    )


def _critique_prompt(question: str, proposals: List[Dict]) -> str:
    proposal_block = "\n\n".join(
        f"--- PROPOSAL {i} by {p['provider']} ({p['model']}) ---\n{p['text']}"
        for i, p in enumerate(proposals, 1)
    )
    return (
        f"Critique these {len(proposals)} proposals to '{question}':\n\n"
        f"{proposal_block}\n\n"
        "For each: what's right, what's wrong or missing, in 2-4 sentences."
    )


def council_ask(question: str, rounds: int = DEFAULT_ROUNDS,
                members: Optional[List[Dict]] = None,
                timeout: float = DEFAULT_TIMEOUT,
                ask_fn=None, synthesize_fn=None) -> Dict:
    """Run council deliberation. Returns a rich result dict.

    ask_fn(provider, model, prompt, timeout) defaults to a thin wrapper over
    core.hive._ask_one; synthesize_fn(question, answers) defaults to
    core.hive.synthesize_consensus. Both are injectable for tests.
    """
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "empty question",
                "next_steps": "Provide a question for the council."}
    rounds = max(1, int(rounds or 1))
    timeout = float(timeout or DEFAULT_TIMEOUT)

    if members is None:
        members = get_council_members()
    if not members:
        return _no_members_result()

    ask_fn = ask_fn or _default_ask_fn
    synthesize_fn = synthesize_fn or synthesize_consensus

    round_results: List[Dict] = []
    attributions: List[Dict] = []
    calls_made = 0
    previous = {}  # provider -> last successful proposal text

    for r in range(1, rounds + 1):
        # ---- proposal phase (parallel) ----
        proposals: List[Dict] = []
        with ThreadPoolExecutor(max_workers=max(1, len(members))) as ex:
            futs = {}
            for m in members:
                own = previous.get(m["provider"])
                if r == 1 or not own:
                    prompt = _direct_prompt(question)
                else:
                    critiques = round_results[-1]["critiques"] if round_results else []
                    prompt = _revision_prompt(question, own, critiques)
                futs[ex.submit(ask_fn, m["provider"], m["model"], prompt, timeout)] = m
            for fut in as_completed(futs):
                m = futs[fut]
                try:
                    res = fut.result()
                    if not isinstance(res, dict):
                        res = {"provider": m["provider"], "model": m["model"],
                               "ok": False, "error": "ask_fn returned non-dict"}
                except Exception as e:  # ask_fn isn't supposed to raise; be honest
                    res = {"provider": m["provider"], "model": m["model"],
                           "ok": False, "error": f"{type(e).__name__}: {e}"}
                calls_made += 1
                attributions.append(res)
                proposals.append(res)
        ok_proposals = [p for p in proposals if p.get("ok") and p.get("text")]
        for p in ok_proposals:
            previous[p["provider"]] = p["text"]
        proposals.sort(key=lambda p: p.get("provider", ""))

        # ---- critique phase (parallel, skipped after the last round) ----
        critiques: List[Dict] = []
        if r < rounds and ok_proposals:
            critique_prompt = _critique_prompt(question, ok_proposals)
            with ThreadPoolExecutor(max_workers=max(1, len(members))) as ex:
                futs = {ex.submit(ask_fn, m["provider"], m["model"],
                                  critique_prompt, timeout): m
                        for m in members}
                for fut in as_completed(futs):
                    m = futs[fut]
                    try:
                        res = fut.result()
                        if not isinstance(res, dict):
                            res = {"provider": m["provider"], "model": m["model"],
                                   "ok": False, "error": "ask_fn returned non-dict"}
                    except Exception as e:
                        res = {"provider": m["provider"], "model": m["model"],
                               "ok": False, "error": f"{type(e).__name__}: {e}"}
                    calls_made += 1
                    attributions.append(res)
                    critiques.append(res)
            critiques.sort(key=lambda c: c.get("provider", ""))
        round_results.append({"proposals": proposals, "critiques": critiques})

    final_proposals = [p for p in round_results[-1]["proposals"]
                       if p.get("ok") and p.get("text")]
    if not final_proposals:
        return {"ok": False, "error": "all proposals failed",
                "rounds": round_results, "attributions": attributions,
                "calls_made": calls_made, "members": members,
                "next_steps": "Check /connections and try again."}

    calls_made += 1
    try:
        consensus = synthesize_fn(question, final_proposals)
        if not isinstance(consensus, dict) or not consensus.get("text"):
            raise ValueError("synthesizer returned no text")
        final_text = str(consensus["text"]).strip()
        method = consensus.get("method", "synthesized")
    except Exception as e:
        # Never discard the proposals — show them attributed instead.
        sections = "\n\n".join(
            f"--- {p['provider'].upper()} ({p['model']}) ---\n{p['text']}"
            for p in final_proposals
        )
        final_text = (f"_Consensus synthesis failed ({e}) — showing individual "
                      f"model answers:_\n\n{sections}")
        method = "concatenated"

    return {"ok": True, "final": final_text, "method": method,
            "rounds": round_results, "attributions": attributions,
            "calls_made": calls_made, "members": members}


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _trunc(text: str, limit: int = 600) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + "…"


def display_council_result(res: Dict) -> None:
    """Render a council_ask result: per-round panels, critiques dimmed,
    final answer highlighted. Failures use the shared ui_error panel."""
    if not res.get("ok"):
        from core.ui import ui_error
        console.print(ui_error(
            "Council deliberation failed",
            res.get("error", "unknown error"),
            why="",
            next_steps=res.get("next_steps", "Check /connections and try again."),
        ))
        return

    console.print(Panel(
        res["final"],
        title="[bold green]🏛️ Council decision[/bold green]",
        border_style="green",
    ))

    for i, rnd in enumerate(res.get("rounds", []), 1):
        lines = []
        for p in rnd.get("proposals", []):
            tag = f"[bold]{p.get('provider', '?')}[/bold] [dim]({p.get('model', '?')})[/dim]"
            if p.get("ok") and p.get("text"):
                lines.append(f"{tag}\n{_trunc(p['text'])}")
            else:
                lines.append(f"{tag}\n[red]✗ {p.get('error', 'failed')}[/red]")
            lines.append("")
        if rnd.get("critiques"):
            lines.append("[dim]── critiques ──[/dim]")
            for c in rnd["critiques"]:
                who = f"{c.get('provider', '?')} ({c.get('model', '?')})"
                if c.get("ok") and c.get("text"):
                    lines.append(f"[dim]{who}:[/dim] [dim italic]{_trunc(c['text'])}[/dim italic]")
                else:
                    lines.append(f"[dim]{who}: ✗ {c.get('error', 'failed')}[/dim]")
        console.print(Panel(
            "\n".join(lines).rstrip(),
            title=f"[bold cyan]Round {i}[/bold cyan]",
            border_style="cyan",
        ))

    table = Table(show_header=True, header_style="bold dim", box=None)
    table.add_column("Provider"); table.add_column("Model")
    table.add_column("Kind"); table.add_column("Status")
    proposals_ids = {id(p) for rnd in res.get("rounds", []) for p in rnd.get("proposals", [])}
    for a in res.get("attributions", []):
        status = "[green]✓[/green]" if a.get("ok") else \
            f"[red]✗ {str(a.get('error', ''))[:60]}[/red]"
        kind = "proposal" if id(a) in proposals_ids else "critique"
        table.add_row(a.get("provider", "?"), a.get("model", "?"), kind, status)
    console.print(table)
    console.print(f"[dim]{res.get('calls_made', '?')} model calls across "
                  f"{len(res.get('members', []))} providers.[/dim]")


# ---------------------------------------------------------------------------
# /council command handler (wired by the parent in cli.py)
# ---------------------------------------------------------------------------

def handle_council_command(args: str) -> None:
    """Parse ``--rounds N --members p1,p2 <question>`` and run the council.

    Warns about the expected call cost up front and asks for confirmation
    unless auto-approve is on.
    """
    rounds = DEFAULT_ROUNDS
    member_names: Optional[List[str]] = None
    question_parts: List[str] = []
    tokens = shlex.split(args or "")
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("--rounds", "-r") and i + 1 < len(tokens):
            try:
                rounds = max(1, int(tokens[i + 1]))
            except ValueError:
                console.print(f"[yellow]Ignoring bad --rounds value "
                              f"'{tokens[i + 1]}'.[/yellow]")
            i += 2
        elif tok.startswith("--rounds="):
            try:
                rounds = max(1, int(tok.split("=", 1)[1]))
            except ValueError:
                console.print(f"[yellow]Ignoring bad --rounds value '{tok}'.[/yellow]")
            i += 1
        elif tok == "--members" and i + 1 < len(tokens):
            member_names = [p.strip() for p in tokens[i + 1].split(",") if p.strip()]
            i += 2
        elif tok.startswith("--members="):
            member_names = [p.strip() for p in tok.split("=", 1)[1].split(",") if p.strip()]
            i += 1
        else:
            question_parts.append(tok)
            i += 1

    question = " ".join(question_parts).strip()
    if not question:
        question = Prompt.ask("Question for the council")
    if not (question or "").strip():
        from core.ui import ui_error
        console.print(ui_error("No question", "The council needs a question to deliberate on.",
                               next_steps="Run /council <your question>."))
        return

    members = get_council_members({"council_members": member_names}) \
        if member_names else get_council_members()
    if not members:
        display_council_result(_no_members_result())
        return

    estimate = estimate_calls(len(members), rounds)
    console.print(
        f"[yellow]⚠️  Council mode will make ~{estimate} model calls "
        f"across {len(members)} providers and {rounds} rounds.[/yellow]"
    )
    if not is_auto_approve():
        if not confirm("Start council deliberation?", default=False):
            console.print("[dim]Council deliberation cancelled.[/dim]")
            return

    display_council_result(council_ask(question, rounds=rounds, members=members))
