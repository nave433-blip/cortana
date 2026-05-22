import json
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()
PLANS_DIR = Path.home() / ".jarvis" / "plans"

def ensure_plans_dir():
    PLANS_DIR.mkdir(parents=True, exist_ok=True)

def save_plan(plan_name: str, content: str):
    ensure_plans_dir()
    path = PLANS_DIR / f"{plan_name}.md"
    with open(path, "w") as f:
        f.write(content)
    return path

def display_plan(plan_name: str):
    path = PLANS_DIR / f"{plan_name}.md"
    if not path.exists():
        console.print(f"[red]Plan '{plan_name}' not found.[/red]")
        return
    
    with open(path, "r") as f:
        console.print(Panel(Markdown(f.read()), title=f"Plan: {plan_name}", border_style="cyan"))

def get_active_plan():
    # Helper to check if a plan is currently marked as "active" in state
    pass
