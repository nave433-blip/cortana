import subprocess
from rich.console import Console

console = Console()

def launch_tool(tool_name):
    """
    Launch specialized AI tools via Ollama Cloud.
    Supported: claude-desktop, claude, openclaw, hermes, opencode, codex, copilot, droid, pi
    """
    valid_tools = {
        "claude-desktop": "ollama launch claude-desktop",
        "claude": "ollama launch claude",
        "openclaw": "ollama launch openclaw",
        "hermes": "ollama launch hermes",
        "opencode": "ollama launch opencode",
        "codex": "codex",
        "copilot": "copilot",
        "droid": "droid",
        "pi": "pi",
        "pool": "pool"
    }

    if tool_name not in valid_tools:
        return f"Error: '{tool_name}' is not a recognized launcher command."

    cmd = valid_tools[tool_name]
    console.print(f"[bold cyan]🚀 Launching {tool_name.title()}...[/bold cyan]")
    
    # We run in a new terminal window or background if possible, 
    # but for simplicity, we'll run it and return the intent.
    try:
        # Using Popen to not block the main JARVIS thread
        subprocess.Popen(cmd, shell=True)
        return f"Successfully initiated launch for {tool_name}."
    except Exception as e:
        return f"Launch failed: {e}"
