import subprocess
from rich.console import Console

console = Console()

def launch_tool(tool_name):
    """
    Launch specialized AI tools via direct CLI or Ollama Cloud.
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
        "pool": "pool",
        "aider": "aider",
        "interpreter": "interpreter",
        "gpt-engineer": "gpt-engineer",
        "mentat": "mentat",
        "micro": "micro",
        "neovim": "nvim"
    }

    if tool_name not in valid_tools:
        return f"Error: '{tool_name}' is not a recognized launcher command."

    cmd = valid_tools[tool_name]
    console.print(f"[bold cyan]🚀 Launching {tool_name.title()}...[/bold cyan]")
    
    try:
        # Using Popen to not block the main JARVIS thread
        subprocess.Popen(cmd, shell=True)
        return f"Successfully initiated launch for {tool_name}."
    except Exception as e:
        return f"Launch failed: {e}"
