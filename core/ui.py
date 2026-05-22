import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.align import Align
from core.update import CURRENT_VERSION

console = Console()

def set_warp_status(text: str):
    """Set the terminal tab title (OSC 2) for Warp and other compatible terminals."""
    # Only if in a TTY to avoid polluting logs
    if sys.stdout.isatty():
        sys.stdout.write(f"\033]2;{text}\007")
        sys.stdout.flush()

def clear_warp_status():
    """Reset the terminal tab title."""
    set_warp_status("JARVIS")

def display_chat_message(role: str, text: str):
    """Display a message in a Gemini-style high-fidelity ASCII box."""
    from rich.box import ROUNDED
    from rich.panel import Panel
    from rich.markdown import Markdown

    # Clear status when message is displayed
    clear_warp_status()
    
    color = "cyan" if role.lower() == "jarvis" else "green"
    icon = "🧠" if role.lower() == "jarvis" else "👤"
    
    panel = Panel(
        Markdown(text),
        title=f"[bold {color}]{icon} {role.upper()}[/bold {color}]",
        title_align="left",
        border_style=color,
        box=ROUNDED,
        padding=(1, 2)
    )
    console.print("\n")
    console.print(panel)

def display_welcome():
    splash_text = f"""
    [bold cyan]JARVIS[/bold cyan] [white]v{CURRENT_VERSION}[/white]
    [dim]The Advanced AI Engineering Suite[/dim]
    
    [bold white]Created by Nave433 (Evan Shipley)[/bold white]
    
    *Type [bold cyan]/[/bold cyan] to see commands | [bold yellow]Ctrl+C[/bold yellow] twice to exit*
    """
    
    console.print(Align.center(Panel(
        Markdown(f"# JARVIS\nCreated by **Nave433 (Evan Shipley)**\n\nVersion: `{CURRENT_VERSION}`"),
        style="bold blue",
        border_style="cyan",
        subtitle="Initializing Systems...",
        expand=False
    )))

def get_main_menu_table():
    table = Table(show_header=False, box=None)
    table.add_column("Command", style="cyan", justify="right")
    table.add_column("Description", style="white")
    
    table.add_row("/chat", "Consult JARVIS for technical advice or code explanation")
    table.add_row("/fix", "Autonomous research & repair loop for project bugs")
    table.add_row("/analyze", "Deep health audit: lines, complexity, and file hotspots")
    table.add_row("/analyze-file", "Focused security and performance audit on a single file")
    table.add_row("/locate", "Global system search for files and directories")
    table.add_row("/troubleshoot", "Warp-style Agent Mode: Run command and auto-fix errors")
    table.add_row("/network", "Fing-style local network discovery and port scanning")
    table.add_row("/ssh", "Execute commands on remote servers via agentic SSH")
    table.add_row("/server", "Monitor local ports, process stats, and manage services")
    table.add_row("/undo", "Safety rollback: Revert the last file change made by JARVIS")
    table.add_row("/dashboard", "Launch live multi-window system monitoring interface")
    table.add_row("/memory", "Search or manage the persistent vector knowledge base")
    table.add_row("/personality", "Switch between Professional, Sarcastic, Concise, or Mentor vibes")
    table.add_row("/models", "Intelligent provider switcher (Ollama, NVIDIA, OpenAI, etc.)")
    table.add_row("/launch", "Spin up specialized AI agents (Claude Code, Hermes, Copilot CLI)")
    table.add_row("/model", "Detailed status of active model, provider, and current quota")
    table.add_row("/cloud", "Bridge to Google Drive, Dropbox, and iCloud storage")
    table.add_row("/focus", "Set a specific path as the primary work context for the agent")
    table.add_row("/help", "Access detailed system documentation and role guide")
    table.add_row("/exit", "Secure shutdown of all background threads and exit")
    
    return Panel(table, title="[bold white]System Commands & Capabilities[/bold white]", border_style="blue", expand=False)
