import subprocess

UNSAFE_PATTERNS = ["rm ", "sudo ", "mv ", "chmod ", "chown ", "dd ", "mkfs ", "> /dev/", ":(){ :|:& };:"]

def _load_allowlist():
    """Read the optional "shell_allowlist" config key.

    Returns the list of allowed command prefixes, or None when allowlist mode
    is off (key missing or empty). Any config read failure also means off, so
    the legacy blocklist behavior always stays available.
    """
    try:
        from core.config import load_config
        allowlist = load_config().get("shell_allowlist")
    except Exception:
        return None
    return allowlist or None

def run(cmd, confirm=False, allowlist="auto", sandbox=False):
    """Execute a shell command, returning a result dict.

    allowlist controls allowlist mode:
      - "auto" (default): read the "shell_allowlist" config key. Missing or
        empty means allowlist mode is OFF and the legacy blocklist applies.
      - None: force allowlist mode off (legacy blocklist behavior).
      - a list of prefixes: only commands whose stripped text starts with one
        of the prefixes are executed; anything else is refused with
        {"status": "blocked", ...}.

    Allowlist mode is a superset restriction: the UNSAFE_PATTERNS blocklist
    still applies to allowed commands exactly as before. Default behavior is
    unchanged (allowlist off).

    sandbox=True routes execution through tools.sandbox.run_sandboxed()
    (Linux-only; fresh temp dir, rlimits, optional bwrap isolation).
    Default False — plain subprocess execution is unchanged.
    """
    if allowlist == "auto":
        allowlist = _load_allowlist()
    if allowlist:
        stripped = cmd.strip()
        if not any(stripped.startswith(prefix) for prefix in allowlist):
            return {"status": "blocked",
                    "error": f"Command not in shell allowlist: {cmd!r}"}

    is_unsafe = any(pattern in cmd for pattern in UNSAFE_PATTERNS)

    if is_unsafe and not confirm:
        return {"status": "needs_confirmation", "command": cmd}

    if sandbox:
        from tools.sandbox import run_sandboxed
        return run_sandboxed(cmd, timeout=180).to_dict()

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
        output = result.stdout
        error = result.stderr
        return {
            "stdout": output,
            "stderr": error,
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 3 minutes (180s) of no output."}
    except Exception as e:
        return {"error": str(e)}

def run_simple(cmd, confirm=False, allowlist="auto", sandbox=False):
    """Legacy wrapper for simple output."""
    res = run(cmd, confirm=confirm, allowlist=allowlist, sandbox=sandbox)
    if isinstance(res, dict):
        if res.get("sandboxed"):
            if res.get("error"):
                return f"Sandbox error: {res['error']}"
            out = (res.get("stdout") or "").strip()
            if res.get("timed_out"):
                return f"Timed out in sandbox ({res.get('backend')}).\n{out}"
            if res.get("return_code") != 0:
                err = (res.get("stderr") or "").strip()
                return f"Exit {res['return_code']} [sandbox/{res.get('backend')}]:\n{err or out}"
            return out or "Success (No output)"
        if res.get("return_code") == 0:
            return res.get("stdout") or "Success (No output)"
        if res.get("status") == "blocked":
            return f"Blocked: {res.get('error')}"
        return f"Error ({res.get('return_code')}): {res.get('stderr')}"
    return res
