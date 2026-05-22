import shlex
import subprocess
import difflib
import logging
import json
import time
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger("jarvis.command_handler")
logging.basicConfig(level=logging.INFO)

class CommandError(Exception):
    pass

class CommandHandler:
    def __init__(self, llm_client=None, allowed_shell: Optional[List[str]] = None, shell_timeout: int = 20):
        """
        llm_client: optional object you can call to parse free text into structured intent.
        allowed_shell: optional whitelist of shell command names (e.g., ["ls","grep","python"])
        shell_timeout: seconds for subprocess.run timeout
        """
        self._registry: Dict[str, Dict[str, Any]] = {}
        self.llm_client = llm_client
        self.shell_timeout = shell_timeout
        self.allowed_shell = allowed_shell  # if None -> no whitelist (be careful)

    def register(self, name: str, func: Callable[..., Any], aliases: Optional[List[str]] = None, help: str = ""):
        entry = {"func": func, "aliases": set(aliases or []), "help": help}
        self._registry[name] = entry
        for a in aliases or []:
            self._registry[a] = entry  # alias points to same entry

    def list_commands(self):
        # unique commands (dedupe by func reference)
        seen = set()
        out = []
        for name, meta in self._registry.items():
            if id(meta["func"]) in seen:
                continue
            seen.add(id(meta["func"]))
            out.append((name, meta["help"]))
        return out

    def _tokenize(self, text: str) -> List[str]:
        return shlex.split(text)

    def _match_known(self, tokens: List[str]):
        if not tokens:
            return None, None
        candidate = tokens[0]
        if candidate in self._registry:
            return candidate, tokens[1:]
        # fuzzy match against registry keys
        keys = list(self._registry.keys())
        close = difflib.get_close_matches(candidate, keys, n=1, cutoff=0.6)
        if close:
            return close[0], tokens[1:]
        return None, None

    def _call_llm_parse(self, text: str) -> Dict[str, Any]:
        """
        Fallback that asks an LLM to parse the user's free text into a small JSON:
          {"type": "internal"|"shell"|"help", "target": "command_name_or_shell", "args": ["..."], "confirm": bool}
        Replace this stub with a real Ollama/Gemini/LLM call.
        """
        if self.llm_client:
            # Example expected interface: llm_client.parse_intent(text) -> dict
            return self.llm_client.parse_intent(text)

        # Basic heuristic fallback: if text begins with a known shell-ish token, treat as shell
        tokens = text.strip().split()
        if not tokens:
            return {"type": "help", "target": "help", "args": []}
        if tokens[0].startswith("scan") or tokens[0] in ("ls","cat","grep","python","pip","git"):
            return {"type": "shell", "target": " ".join(tokens), "args": []}
        # Otherwise attempt to map to internal by fuzzy match
        candidate = difflib.get_close_matches(tokens[0], list(self._registry.keys()), n=1, cutoff=0.5)
        if candidate:
            return {"type": "internal", "target": candidate[0], "args": tokens[1:], "confirm": False}
        # fallback: ask to run as shell but request confirm
        return {"type": "shell", "target": " ".join(tokens), "args": [], "confirm": True}

    def _execute_shell(self, cmd: str, confirm: bool = False) -> Dict[str, Any]:
        if confirm:
            raise CommandError("Execution requires user confirmation (confirm=True).")

        # very small whitelist check if provided
        if self.allowed_shell:
            try:
                first = shlex.split(cmd)[0]
            except Exception:
                raise CommandError("Invalid shell command tokenization.")
            if first not in self.allowed_shell:
                raise CommandError(f"'{first}' is not allowed by shell whitelist.")

        try:
            proc = subprocess.run(cmd, shell=False if isinstance(cmd, (list, tuple)) else False,
                                  args=shlex.split(cmd) if isinstance(cmd, str) else cmd,
                                  capture_output=True, text=True, timeout=self.shell_timeout)
            return {"rc": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        except subprocess.TimeoutExpired:
            raise CommandError("Shell command timed out.")
        except Exception as e:
            raise CommandError(f"Shell execution failed: {e}")

    def handle(self, text: str, confirm_shell: bool = False) -> Dict[str, Any]:
        text = text.strip()
        if not text:
            return {"ok": False, "error": "empty command"}

        tokens = self._tokenize(text)
        matched, args = self._match_known(tokens)

        if matched:
            entry = self._registry[matched]
            func = entry["func"]
            try:
                result = func(args)
                return {"ok": True, "type": "internal", "command": matched, "result": result}
            except Exception as e:
                logger.exception("internal command raised exception")
                return {"ok": False, "error": f"internal command error: {e}"}

        # unknown command -> call LLM fallback to interpret
        parsed = self._call_llm_parse(text)
        t = parsed.get("type")
        if t == "internal":
            target = parsed.get("target")
            args = parsed.get("args", [])
            if target in self._registry:
                try:
                    res = self._registry[target]["func"](args)
                    return {"ok": True, "type": "internal", "command": target, "result": res}
                except Exception as e:
                    logger.exception("internal command failed after LLM resolution")
                    return {"ok": False, "error": f"internal command error: {e}"}
            else:
                return {"ok": False, "error": f"LLM suggested internal command '{target}' not found."}

        if t == "shell":
            cmd = parsed.get("target")
            confirm = parsed.get("confirm", False)
            if confirm and not confirm_shell:
                return {"ok": False, "error": "confirmation required to execute shell command", "confirm": True, "command": cmd}
            try:
                out = self._execute_shell(cmd, confirm=(confirm and not confirm_shell))
                return {"ok": True, "type": "shell", "command": cmd, "result": out}
            except CommandError as ce:
                return {"ok": False, "error": str(ce)}

        if t == "help":
            return {"ok": True, "type": "help", "commands": self.list_commands()}

        return {"ok": False, "error": "unknown parsed result from LLM"}

# Example internal commands
def cmd_scan(args: List[str]):
    # Minimal example: return structured response instead of running a risky operation
    path = args[0] if args else "/"
    # implement your scanning logic here; placeholder:
    return {"action": "scan", "path": path, "found": ["file1.py", "tool.sh"]}

def cmd_add_feature(args: List[str]):
    feature_desc = " ".join(args) or "<no description>"
    # placeholder: create TODO or open an editor / create issue
    return {"action": "add_feature", "description": feature_desc, "status": "queued"}

# Example of wiring up the handler
def example_usage():
    handler = CommandHandler()
    handler.register("scan", cmd_scan, aliases=["search"], help="Scan a path for useful code")
    handler.register("add-feature", cmd_add_feature, aliases=["addfeature", "feature"], help="Add a new feature request")
    # handle some inputs
    print(handler.handle("scan /etc"))
    print(handler.handle("search /usr/bin"))
    print(handler.handle("add feature for n4v3r41n program"))
    # unknown -> LLM fallback stub will attempt to treat as shell or internal
    print(handler.handle("run git status"))
    return handler

if __name__ == "__main__":
    example_usage()