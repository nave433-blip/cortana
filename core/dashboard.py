import time
import psutil
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, BarColumn, TextColumn
from core.config import get_env_with_config
from tools.analytics import project_summary
import os

console = Console()

def make_layout():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
    )
    layout["main"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=1),
    )
    layout["left"].split_column(
        Layout(name="stats", ratio=1),
        Layout(name="hotspots", ratio=1),
    )
    layout["right"].split_column(
        Layout(name="system"),
        Layout(name="focus"),
    )
    return layout

class Dashboard:
    def __init__(self):
        self.layout = make_layout()
        self.focus_path = "."

    def update_header(self):
        provider = get_env_with_config("provider") or "ollama"
        self.layout["header"].update(Panel(f"JARVIS SOVEREIGN DASHBOARD | Provider: [bold cyan]{provider.upper()}[/bold cyan] | Target: [bold yellow]{os.path.abspath(self.focus_path)}[/bold yellow]", border_style="cyan"))

    def update_stats(self):
        summary = project_summary(self.focus_path)
        table = Table(expand=True, box=None)
        table.add_column("Metric", style="white")
        table.add_column("Value", style="bold green")
        table.add_row("Total Files", str(summary["total_files"]))
        table.add_row("Total Lines", str(summary["total_lines"]))
        
        lang_str = ", ".join([f"{k}: {v}" for k, v in sorted(summary["languages"].items(), key=lambda x: x[1], reverse=True)[:5]])
        table.add_row("Languages", lang_str)
        
        self.layout["stats"].update(Panel(table, title="Project Overview", border_style="green"))

        # Update hotspots
        h_table = Table(expand=True, box=None)
        h_table.add_column("Complexity Hotspot", style="white")
        h_table.add_column("Score", style="bold red")
        for h in sorted(summary["hotspots"], key=lambda x: x["score"], reverse=True)[:8]:
            h_table.add_row(os.path.basename(h["path"]), str(h["score"]))
        
        self.layout["hotspots"].update(Panel(h_table, title="Refactor Candidates", border_style="red"))

    def update_system(self):
        # Real-time system monitoring
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        
        table = Table(expand=True, box=None)
        table.add_column("Component")
        table.add_column("Load")
        
        cpu_color = "red" if cpu > 80 else "yellow" if cpu > 50 else "green"
        mem_color = "red" if mem > 80 else "yellow" if mem > 50 else "green"
        
        table.add_row("CPU", f"[{cpu_color}]{cpu}%[/]")
        table.add_row("RAM", f"[{mem_color}]{mem}%[/]")
        table.add_row("DISK", f"{disk}%")
        
        self.layout["system"].update(Panel(table, title="Live System Metrics", border_style="magenta"))

    def update_focus(self):
        try:
            files = [f for f in os.listdir(self.focus_path) if not f.startswith(".")]
            file_list = "\n".join([f"📄 {f}" for f in files[:10]])
            self.layout["focus"].update(Panel(file_list, title="Directory Preview", border_style="blue"))
        except:
            self.layout["focus"].update(Panel("Access Denied", title="Directory Preview"))

    def run(self):
        with Live(self.layout, refresh_per_second=1, screen=True):
            while True:
                self.update_header()
                self.update_stats()
                self.update_system()
                self.update_focus()
                time.sleep(1)
