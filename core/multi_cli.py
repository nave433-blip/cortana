import subprocess
import json
from rich.console import Console

console = Console()

def query_ollama_cli(prompt: str) -> str:
    """Executes a prompt via local Ollama CLI."""
    try:
        cmd = ["ollama", "run", "llama3", prompt]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.stdout if result.returncode == 0 else ""
    except Exception as e:
        console.print(f"[dim]Ollama CLI failed: {e}[/dim]")
        return ""

def query_hive_mind(task: str) -> str:
    """Queries remote P2P nodes for task resolution."""
    from core.p2p import scan_for_jarvis_peers, send_remote_command
    peers = scan_for_jarvis_peers()
    for peer in peers:
        res = send_remote_command(peer, "think", {"task": task})
        if res.get("ok"):
            data = json.loads(res.get("data", "{}"))
            return data.get("text", "")
    return ""
