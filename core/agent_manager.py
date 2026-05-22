import subprocess
import shutil
from rich.console import Console

console = Console()

AGENT_REGISTRY = {
    "Hermes": {"install": "pip install nous-hermes", "check": "hermes --version"},
    "OpenClaw": {"install": "pip install openclaw", "check": "openclaw --version"},
    "OpenCode": {"install": "pip install opencode", "check": "opencode --version"},
    "Codex": {"install": "pip install openai-codex", "check": "codex --version"},
    "Copilot CLI": {"install": "gh extension install github/gh-copilot", "check": "gh copilot --version"},
    "Droid": {"install": "pip install factory-droid", "check": "droid --version"},
    "Pi": {"install": "pip install pi-agent", "check": "pi --version"},
    "Pool": {"install": "pip install poolside-pool", "check": "pool --version"},
}

def check_and_install_agents():
    for name, cmds in AGENT_REGISTRY.items():
        if not shutil.which(cmds["check"].split()[0]):
            console.print(f"[yellow]⚠️ Agent '{name}' not found. Installing...[/yellow]")
            try:
                subprocess.check_call(cmds["install"].split())
                console.print(f"[green]✅ Agent '{name}' installed.[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed to install agent '{name}': {e}[/red]")
        else:
            console.print(f"[dim][green]✓ Agent '{name}' detected.[/green][/dim]")
