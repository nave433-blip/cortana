"""
Lightweight code-understanding helpers for Python source files.

- AST-based extraction: functions, classes, imports, docstrings, line ranges.
- Simple heuristics and metrics (line counts, TODO/FIXME).
- Helpers to call the LLM (think) with a structured prompt to explain or propose a patch.
- Unified-diff helper and safe apply (creates a .bak backup).
"""

import ast
import os
import textwrap
import difflib
import re
from typing import Dict, List, Optional, Tuple

# Import your existing think() wrapper (used by cli.py)
try:
    from core.brain import think
except Exception:
    # If unavailable at import-time, defer to callers that import think themselves.
    think = None

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def parse_python_source(source: str) -> ast.Module:
    return ast.parse(source)

def extract_definitions(path: str) -> List[Dict]:
    """Return list of top-level functions and classes with metadata."""
    try:
        src = read_file(path)
        mod = parse_python_source(src)
        lines = src.splitlines()
        defs = []
        for node in mod.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", None)
                if start is None:
                    continue
                # safe end calculation
                end = end or start
                src_snippet = "\n".join(lines[start-1:end])
                doc = ast.get_docstring(node) or ""
                defs.append({
                    "type": type(node).__name__,
                    "name": getattr(node, "name", "<lambda>"),
                    "start": start,
                    "end": end,
                    "doc": doc,
                    "snippet": src_snippet,
                })
        return defs
    except Exception as e:
        return [{"type": "error", "error": str(e)}]

def file_summary(path: str, max_chars: int = 2000) -> str:
    """Return a compact deterministic summary of the file using AST and heuristics."""
    try:
        src = read_file(path)
        lines = src.splitlines()
        total_lines = len(lines)
        defs = extract_definitions(path)
        imports = []
        try:
            mod = parse_python_source(src)
            for node in mod.body:
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append(n.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for n in node.names:
                        imports.append(f"{module}.{n.name}")
        except Exception:
            imports = []

        todos = [ln for ln in lines if "TODO" in ln or "FIXME" in ln]
        summary_lines = [
            f"File: {os.path.basename(path)}",
            f"Path: {path}",
            f"Total lines: {total_lines}",
            f"Top-level defs: {len(defs)}",
            f"Imports: {', '.join(imports[:8]) or 'none'}",
            f"TODO/FIXME lines: {len(todos)}",
            "",
            "Definitions (name: start-end, docstring summary):",
        ]
        for d in defs[:20]:
            if d.get("type") == "error": continue
            ds = (d["doc"].strip().splitlines()[0][:100] + "...") if d["doc"] else ""
            summary_lines.append(f"- {d['type']} {d['name']}: {d['start']}-{d['end']}  doc: {ds}")
        summary = "\n".join(summary_lines)
        if len(summary) > max_chars:
            return summary[:max_chars] + "..."
        return summary
    except Exception as e:
        return f"Error summarizing {path}: {e}"

def make_unified_diff(old: str, new: str, filename: str = "file.py") -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    ud = difflib.unified_diff(old_lines, new_lines, fromfile=filename, tofile=filename, lineterm="")
    return "".join(ud)

def safe_apply_new_content(path: str, new_content: str, backup: bool = True) -> Tuple[bool, str]:
    """
    Write new_content to path safely. Create backup path.bak (first time).
    Returns (ok, message).
    """
    if not os.path.exists(path):
        return False, f"Target file not found: {path}"
    try:
        if backup:
            bak = path + ".bak"
            if not os.path.exists(bak):
                with open(bak, "w", encoding="utf-8") as b:
                    b.write(read_file(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True, f"Wrote {path} (backup: {backup})"
    except Exception as e:
        return False, str(e)

def _prepare_prompt_for_patch(path: str, context_lines: int = 2000, instruction: str = "") -> str:
    """
    Build a prompt for the LLM that contains:
      - short deterministic summary (AST)
      - a bounded slice of the file content
      - a clear instruction to return ONLY the full modified file content in triple-backticks
        or a unified diff (we prefer full file content to simplify apply).
    """
    src = read_file(path)
    summary = file_summary(path)
    snippet = "\n".join(src.splitlines()[:context_lines])
    prompt = textwrap.dedent(f"""
    You are an expert Python engineer and code reviewer. I will give you a Python file and an instruction.
    First: provide a short bulleted list (max 6 bullets) of the most important issues or improvements you see.
    Second: produce a suggested patch that implements the requested instruction.

    File summary:
    {summary}

    Instruction:
    {instruction}

    File content (first {context_lines} lines):
    ```python
    {snippet}
    ```

    Constraints for the patch:
    - Return only a single code block with the full updated file content wrapped in triple backticks and labeled ```python```.
    - Do NOT include extra surrounding text, do NOT include numbered steps.
    - If you think no change is needed, return the original file content in the same format.
    - Keep formatting and imports consistent.
    """).strip()
    return prompt

def suggest_patch_via_llm(path: str, instruction: str, model: Optional[str] = None, max_context_chars: int = 2000) -> Dict:
    """
    Ask the LLM (using think) to suggest a full-file replacement based on the instruction.
    Returns a dict: {ok, summary_bullets, suggested_content, unified_diff}
    """
    if think is None:
        return {"ok": False, "error": "LLM wrapper 'think' not available at import time."}
    prompt = _prepare_prompt_for_patch(path, context_lines=max_context_chars, instruction=instruction)
    # think() now returns a dict
    res = think("", prompt)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error"), "raw_resp": res}

    resp = res.get("text", "")
    # Extract the code block (simple heuristics)
    suggested = _extract_first_python_block(resp)
    if not suggested:
        # Fallback: assume whole response is the content
        suggested = resp
    try:
        old = read_file(path)
        ud = make_unified_diff(old, suggested, filename=os.path.basename(path))
        return {"ok": True, "summary": "LLM-generated patch", "suggested": suggested, "unified_diff": ud, "raw_resp": resp}
    except Exception as e:
        return {"ok": False, "error": str(e), "raw_resp": resp}

def _extract_first_python_block(text: str) -> Optional[str]:
    """
    Very small, robust extractor: finds first triple-backtick block labelled python or not,
    returns inner content. Returns None if not found.
    """
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.S | re.I)
    if m:
        return m.group(1).strip()
    # Try fenced but unlabeled
    m2 = re.search(r"```\n(.*?)```", text, re.S)
    if m2:
        return m2.group(1).strip()
    return None
