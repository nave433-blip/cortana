import subprocess
import shutil
from rich.console import Console

console = Console()

# NOTE: install commands use each tool's real distribution channel
# (npm / curl / gh extension) — not PyPI.
AGENT_REGISTRY = {
    "Hermes": {
        "install": "curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash",
        "check": "hermes --version",
    },
    "OpenClaw": {
        "install": "npm install -g openclaw@latest",
        "check": "openclaw --version",
    },
    "OpenCode": {
        "install": "npm install -g opencode-ai",
        "check": "opencode --version",
    },
    "Codex": {
        "install": "npm install -g @openai/codex",
        "check": "codex --version",
    },
    "Copilot CLI": {
        "install": "gh extension install github/gh-copilot",
        "check": "gh copilot --version",
    },
    "Droid": {
        "install": "npm install -g droid",
        "check": "droid --version",
    },
    "Pi": {
        "install": "npm install -g @earendil-works/pi-coding-agent",
        "check": "pi --version",
    },
    "Pool": {
        "install": "curl -fsSL https://downloads.poolside.ai/pool/install.sh | sh",
        "check": "pool --version",
    },
}

def check_and_install_agents():
    for name, cmds in AGENT_REGISTRY.items():
        if not shutil.which(cmds["check"].split()[0]):
            console.print(f"[yellow]⚠️ Agent '{name}' not found. Installing...[/yellow]")
            try:
                subprocess.check_call(cmds["install"], shell=True)
                console.print(f"[green]✅ Agent '{name}' installed.[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed to install agent '{name}': {e}[/red]")
        else:
            console.print(f"[dim][green]✓ Agent '{name}' detected.[/green][/dim]")
