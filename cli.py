import os
import sys
import time
import json
import subprocess
from typing import Optional, Dict, Any
from typing_extensions import Annotated

# 1. Self-Repairing Dependency Check (runs on CLI invocation, not on import —
#    importing this module as a library must stay side-effect free)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.deps import ensure_all

# 2. Global Self-Repair & Reporting Engine
from core.repair import init_repair_engine

# 3. Auto-Update Check
from core.update import auto_update_check, CURRENT_VERSION


def run_startup_checks() -> None:
    """Heavy startup side effects: only run for real CLI invocations.

    Skipped when JARVIS_SKIP_STARTUP=1 (tests, library use) so that merely
    importing this module never pip-installs packages, hits the network,
    or prompts for input.
    """
    if os.environ.get("JARVIS_SKIP_STARTUP") == "1":
        return
    ensure_all()
    init_repair_engine()
    auto_update_check()

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt, Confirm

# Internal Modules
from core.brain import think, think_structured, get_provider
from core.agent import debug_loop, troubleshoot_loop, forge_loop
from core.config import setup_wizard, get_env_with_config, CONFIG_FILE, load_config, save_config
from core.services import repair_ollama
from core.config import start_periodic_config_maintenance, auto_config_maintenance_once
from core.logger import ErrorLogger
from core.auth import AuthManager
from core.startup import startup_check_and_login
from core.ui import display_welcome, get_main_menu_table, display_chat_message
from core.health import check_system_health, display_health_report, auto_repair_workspace, update_all_repos
from core.repair import auto_check_on_launch
from core.nave_loop import run_nave_loop
from core.handler import CommandHandler
import core.menus as menus

# Prompt Toolkit for slash commands
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML

import warnings
warnings.simplefilter("ignore", SyntaxWarning)

app = typer.Typer(help="🚀 JARVIS: The Ultimate Local AI Coding Assistant", add_completion=False)
console = Console()

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context,
         debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
         skip_startup: bool = typer.Option(False, "--skip-startup", help="Skip dependency/update startup checks")):
    """JARVIS: Your local AI engineer."""
    if skip_startup:
        os.environ["JARVIS_SKIP_STARTUP"] = "1"
    run_startup_checks()
    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        os.environ["LITELLM_LOG"] = "DEBUG"
        console.print("[dim]Debug mode enabled.[/dim]")
    if ctx.invoked_subcommand is None:
        if not CONFIG_FILE.exists():
            console.print("[yellow]No configuration found. Starting setup...[/yellow]")
            setup_wizard()
        interactive()

# Initialize Advanced Handler
handler = CommandHandler()

from core.gemini_box import session as gemini_session

COMMANDS = [
    "/chat", "/fix", "/forge", "/decode", "/lookup", "/hardware", "/voice", "/watch", "/config", "/init", "/analyze", "/analyze-file",
    "/locate", "/undo", "/dashboard", "/memory", "/personality", "/models", "/focus", "/copilot",
    "/cloud", "/network", "/ssh", "/server", "/troubleshoot", "/free", "/model", "/brain", "/doctor", "/box",
    "/examine-py", "/patch-py", "/ollama",

    "/git", "/nave", "/sync", "/upgrade", "/update", "/connect", "/connections", "/launch", "/plan", "/restart", "/reinstall", "/menu", "/exit",
    "/prompts", "/search", "/clear", "/health", "/google-login", "/google-sync", "/google-register",
    "/google-connect", "/webask", "/multibrain", "/scan-ollama", "/ollama-login", "/p2p-scan", "/p2p-status", "/p2p-edit", "/p2p-read", "/p2p-server", "/p2p-tokens", "/p2p-set-token", "/optimize", "/refine", "/stress-test",
    "/help", "/t",
]

# ... (omitted)

@app.command()
def ollama_cmd(args: Annotated[Optional[str], typer.Argument(help="Ollama CLI arguments")] = None):
    """Direct interface to the local Ollama CLI."""
    import shlex
    import subprocess
    cmd = ["ollama"] + (shlex.split(args) if args else [])
    console.print(f"[dim]Executing: {' '.join(cmd)}[/dim]")
    try:
        subprocess.run(cmd, shell=False)
    except FileNotFoundError:
        console.print("[red]'ollama' executable not found in PATH.[/red]")
    except Exception as e:
        console.print(f"[red]Ollama CLI failed: {e}[/red]")

@app.command()
def scan_ollama():
    """Scan the local network for Ollama instances."""
    from tools.network import scan_network_for_ollama
    from core.config import load_config, save_config
    
    console.print("[cyan]Scanning network for Ollama instances...[/cyan]")
    hosts = scan_network_for_ollama()
    
    if not hosts:
        console.print("[red]No Ollama instances found.[/red]")
        return
        
    console.print(f"[green]Found: {', '.join(hosts)}[/green]")
    if Confirm.ask("Add these to your configuration?"):
        cfg = load_config()
        cfg["ollama_hosts"] = list(set(cfg.get("ollama_hosts", []) + hosts))
        save_config(cfg)
        console.print("[green]✅ Configuration updated.[/green]")

# ... (omitted)

@app.command()
def multibrain(task: Annotated[str, typer.Argument(help="The task or query to reason about using multiple AIs")]):
    """Reason about a task using all connected high-performance AIs."""
    from core.brain import multibrain_think
    res = multibrain_think(task)
    if res.get("ok"):
        display_chat_message("JARVIS", res.get("text"))
    else:
        console.print(f"[red]Error: {res.get('error')}[/red]")

# Register commands for fuzzy matching
for cmd in COMMANDS:
    if cmd != "/exit":
        handler.register(cmd, lambda x: None, help="System command")

def get_bottom_toolbar():
    try:
        cwd = os.getcwd()
        config = load_config()
        model = config.get("jarvis_model", "unknown")
        provider = config.get("provider", "ollama")
        return HTML(f'<style fg="cyan">📁 {cwd}</style> | <style fg="magenta">🧠 {provider.upper()} ({model})</style>')
    except Exception:
        return HTML('<style fg="red">System Initializing...</style>')

@app.command()
def menu():
    """Launch the high-fidelity JARVIS Dashboard Menu."""
    console.clear()
    header = Panel(Markdown(f"# JARVIS SYSTEM INTERFACE\nVersion: `{CURRENT_VERSION}` | Role: `Engineering Sovereign`"), style="bold cyan", border_style="cyan")
    console.print(header)

    grid = Table.grid(expand=True)
    grid.add_column(justify="center"); grid.add_column(justify="center")
    
    core_table = Table(title="[bold magenta]Core AI Agents[/bold magenta]", show_header=True, header_style="bold magenta", border_style="magenta")
    core_table.add_column("Command", style="white"); core_table.add_column("Function", style="dim")
    core_table.add_row("/fix", "Autonomous repair & debugging"); core_table.add_row("/forge", "Hardcore code synthesis & creation"); core_table.add_row("/plan", "Strategic engineering roadmaps"); core_table.add_row("/nave", "Multi-model reasoning & refinement"); core_table.add_row("/copilot", "GitHub Copilot technical advice"); core_table.add_row("/chat", "Direct technical consultation")

    dev_table = Table(title="[bold green]DevOps & Utilities[/bold green]", show_header=True, header_style="bold green", border_style="green")
    dev_table.add_column("Command", style="white"); dev_table.add_column("Function", style="dim")
    dev_table.add_row("/doctor", "System health & self-repair"); dev_table.add_row("/cloud", "Bridge to G-Drive/Dropbox"); dev_table.add_row("/network", "Network discovery & security"); dev_table.add_row("/hardware", "USB & Physical port probing"); dev_table.add_row("/server", "Process & service management")
    
    grid.add_row(core_table, dev_table)
    console.print(grid)

    footer = Panel("[bold white]Settings:[/bold white] /config | [bold white]Accounts:[/bold white] /connect /connections | [bold yellow]RESTART[/bold yellow] | [bold red]REINSTALL[/bold red]", border_style="dim")
    console.print(footer)
    console.print("\n[dim]*Type any command or natural language request below.*[/dim]")

def process_think_res(res: Any, fallback_text: str = "") -> str:
    """Processes the structured dictionary from think() and handles failures."""
    if not isinstance(res, dict):
        return str(res)
        
    if res.get("ok"):
        # Display provider info if available
        if res.get("provider"):
            prov_info = f"Provider: {res.get('provider').upper()}"
            if res.get("model"): prov_info += f" ({res.get('model')})"
            console.print(f"[dim]{prov_info}[/dim]")
        return res.get("text", "")
        
    # Failure case
    console.print(Panel(f"[red]JARVIS could not get an answer from any provider.[/red]\n\nDetails: {res.get('error')}", title="Error", border_style="red"))
    
    # Show short history if present
    hist = res.get("history", [])
    if hist:
        summary = []
        for h in hist:
            if isinstance(h, dict) and "attempt" in h:
                summary.append(f"Primary ({h.get('provider')}): {h.get('result', {}).get('error', 'Unknown error')}")
            elif isinstance(h, dict) and "fallback" in h:
                for f in h.get("history", []):
                    summary.append(f"Fallback ({f.get('provider')}): {f.get('result', {}).get('error', 'Unknown error')}")
        if summary:
            console.print(Panel("\n".join(summary[-6:]), title="Recent Attempts", border_style="magenta"))

    # Ask user whether to run Setup Wizard
    if Confirm.ask("Would you like to run the Setup Wizard to reconfigure providers now?"):
        from core.config import setup_wizard
        setup_wizard()
        return "[yellow]Setup complete. Please try your request again.[/yellow]"
    else:
        console.print("[yellow]Skipping setup. You can run '/setup' later.[/yellow]")
        return fallback_text or "[red]Task failed due to provider disconnection.[/red]"

@app.command()
def interactive():
    """Launch the main interactive Gemini-style prompt."""
    from core.config import verify_and_fix_local_llm
    # JARVIS_SKIP_STARTUP=1 (tests, CI, piped use) also skips interactive()'s
    # own startup routines so piped stdin reaches the REPL instead of being
    # eaten by setup prompts. Real interactive use is unchanged.
    skip_startup = os.environ.get("JARVIS_SKIP_STARTUP") == "1"
    try:
        display_welcome()
        if not skip_startup:
            verify_and_fix_local_llm()
            auto_check_on_launch()
            startup_check_and_login(auto=False)
    except (EOFError, KeyboardInterrupt):
        # Startup prompts need a TTY. With piped/closed stdin (CI, `echo | jarvis`)
        # or Ctrl+C during startup, exit cleanly instead of tracebacking.
        # Interactive TTY behavior is unchanged.
        console.print("\n[yellow]Startup input unavailable — exiting.[/yellow]")
        return

    completer = WordCompleter(COMMANDS, ignore_case=True)
    kb = KeyBindings()
    @kb.add('escape')
    def _(event): event.app.exit(result="/exit")

    session = PromptSession(completer=completer, key_bindings=kb, bottom_toolbar=get_bottom_toolbar)
    style = Style.from_dict({'prompt': 'ansicyan bold', 'bottom-toolbar': 'bg:#1e1e1e #888888'})
    last_ctrl_c = 0

    # Command classification
    PLAIN_COMMANDS = {cmd[1:] for cmd in COMMANDS if cmd.startswith("/")}
    DANGEROUS_PLAIN_CMDS = {"reinstall", "update", "upgrade", "patch-py", "repair-ollama-cmd", "setup", "sync"}

    while True:
        try:
            text = session.prompt('JARVIS > ', style=style).strip()
            last_ctrl_c = 0 
            if not text: continue
            if text in ["/exit", "exit", "quit"]:
                console.print("[yellow]Goodbye, Sir.[/yellow]"); break
            
            try:
                # 1. Intelligent Input Interpretation
                tokens = text.split()
                first_word = tokens[0].lower() if tokens else ""
                
                # Check for "no-slash" command invocation
                if not text.startswith("/") and first_word in PLAIN_COMMANDS:
                    # Guard dangerous commands
                    if first_word in DANGEROUS_PLAIN_CMDS:
                        console.print(Panel(f"[bold yellow]⚠️ DANGEROUS COMMAND DETECTED[/bold yellow]\n\nYou invoked '{first_word}' without a leading '/'.", border_style="yellow"))
                        if not Confirm.ask(f"Are you sure you want to execute '{first_word}'?"):
                            console.print("[yellow]Cancelled.[/yellow]")
                            continue
                    
                    # Transform to slash command for the handler
                    text = "/" + text

                # 2. Use Advanced Handler
                res = handler.handle(text)
                ui_hint = res.get("ui")
                
                if res.get("type") == "chat":
                    display_chat_message("User", res.get("args", text))
                    debug_loop(res.get("args", text))
                    continue

                if res.get("type") == "internal":
                    cmd = res["command"]
                    args = res.get("args", "")
                    
                    prompt_name = None
                    if "@" in args:
                        parts = args.split("@", 1)
                        args = parts[0].strip()
                        prompt_name = parts[1].split()[0]
                    
                    if cmd == "/chat": chat(args or Prompt.ask("Question"), prompt=prompt_name)
                    elif cmd == "/fix": debug_loop(args or Prompt.ask("Issue to fix"), prompt=prompt_name, ui_hint=ui_hint)
                    elif cmd == "/plan": plan(args or Prompt.ask("Task for strategy"))
                    elif cmd == "/forge": forge(args or Prompt.ask("Task to forge"))
                    elif cmd == "/decode": decode(args or Prompt.ask("Content to decode"))
                    elif cmd == "/lookup": lookup(args or Prompt.ask("What to find?"))
                    elif cmd == "/hardware": hardware_menu()
                    elif cmd == "/voice": voice()
                    elif cmd == "/watch": watch()
                    elif cmd == "/config": menus.config_menu()
                    elif cmd == "/init": init()
                    elif cmd == "/analyze": analyze(args or ".")
                    elif cmd == "/analyze-file": analyze_file(args or Prompt.ask("Path to file"), prompt=prompt_name)
                    elif cmd == "/locate": locate(args or Prompt.ask("Search name"))
                    elif cmd == "/network": menus.network_menu()
                    elif cmd == "/ssh": menus.ssh_command(args)
                    elif cmd == "/server": menus.server_menu()
                    elif cmd == "/undo": undo(args or Prompt.ask("Path to undo"))
                    elif cmd == "/dashboard": dashboard()
                    elif cmd == "/memory": menus.memory_menu()
                    elif cmd == "/personality": menus.personality_menu()
                    elif cmd == "/models": menus.models_menu()
                    elif cmd == "/multibrain": multibrain(args or Prompt.ask("Task for multi-brain reasoning"))
                    elif cmd == "/scan-ollama": scan_ollama()
                    elif cmd == "/ollama": ollama_cli(args)
                    elif cmd == "/refine":
                        target = args.split()[0] if args else Prompt.ask("File to refine")
                        test = " ".join(args.split()[1:]) if len(args.split()) > 1 else Prompt.ask("Test command")
                        from core.refinement import refine_loop
                        refine_loop(target, test)
                    elif cmd == "/stress-test":
                        from core.validator import Validator
                        v = Validator()
                        v.run_tests()
                    elif cmd == "/ollama-login": ollama_login()
                    elif cmd == "/p2p-scan": p2p_scan()
                    elif cmd == "/p2p-status": p2p_status()
                    elif cmd == "/p2p-edit":

                        p_ip = args.split()[0] if args else Prompt.ask("Peer IP")
                        p_path = args.split()[1] if args and len(args.split()) > 1 else Prompt.ask("File Path")
                        p_content = " ".join(args.split()[2:]) if args and len(args.split()) > 2 else Prompt.ask("Content")
                        p2p_edit(p_ip, p_path, p_content)
                    elif cmd == "/p2p-read":
                        p_ip = args.split()[0] if args else Prompt.ask("Peer IP")
                        p_path = args.split()[1] if args and len(args.split()) > 1 else Prompt.ask("File Path")
                        p2p_read(p_ip, p_path)
                    elif cmd == "/p2p-server": p2p_server()
                    elif cmd == "/p2p-tokens": p2p_tokens()
                    elif cmd == "/prompts": menus.prompts_menu()
                    elif cmd == "/cloud": menus.cloud_menu()
                    elif cmd == "/connect": menus.connect_menu()
                    elif cmd == "/connections": connections()
                    elif cmd == "/google-login":
                        from core.google_auth import GoogleAuth
                        GoogleAuth.get_credentials()
                    elif cmd == "/google-sync":
                        from core.google_auth import GoogleAuth
                        GoogleAuth.auto_register_flow()
                    elif cmd == "/google-register":
                        from core.google_auth import GoogleAuth
                        GoogleAuth.auto_register_flow()
                    elif cmd == "/google-connect":
                        from core.google_auth import GoogleAuth
                        GoogleAuth.run_flow()
                    elif cmd == "/webask":
                        webask(args or Prompt.ask("Search query"))
                    elif cmd == "/menu": menu()
                    elif cmd == "/reinstall": reinstall()
                    elif cmd == "/model": models_command()
                    elif cmd == "/brain": menus.models_menu()
                    elif cmd == "/launch":
                        from tools.launcher import TOOL_REGISTRY
                        t = args or Prompt.ask("AI tool", choices=list(TOOL_REGISTRY.keys()))
                        launch(tool=t)
                    elif cmd == "/focus": focus(args or Prompt.ask("Path"))
                    elif cmd in ["/troubleshoot", "/t"]: troubleshoot(args or Prompt.ask("Command"), prompt=prompt_name)
                    elif cmd == "/free": show_free_providers()
                    elif cmd == "/doctor": run_doctor()
                    elif cmd == "/git": ai_git(args or Prompt.ask("Git task?"))
                    elif cmd == "/restart": restart()
                    elif cmd == "/search":
                        q = args or Prompt.ask("Search history")
                        results = session.history.get_strings()
                        matches = [s for s in results if q.lower() in s.lower()]
                        console.print(Panel("\n".join(matches[-10:]), title=f"History: {q}"))
                    elif cmd == "/clear": console.clear()
                    elif cmd == "/help": menus.robust_help()
                    elif cmd == "/health": display_health_report(check_system_health())
                    elif cmd in ["/upgrade", "/update"]:
                        from core.update import manual_upgrade
                        manual_upgrade()
                    elif cmd == "/sync": update_all_repos()
                    elif cmd == "/box":
                        box_menu(args)
                    elif cmd == "/examine-py":
                        examine_py(args or Prompt.ask("Path to Python file"))
                    elif cmd == "/patch-py":
                        patch_py(args or Prompt.ask("Path to Python file"))
                    elif cmd == "/nave":
                        from core.nave_loop import run_nave_loop
                        res = run_nave_loop(args or Prompt.ask("Task for NAVE"))
                        if res.get("ok"):
                            console.print(Markdown(res.get("final_answer", "")))
                            if Confirm.ask("Show reasoning summary?"):
                                console.print(Panel(res.get("integrator_json", {}).get("reasoning_summary", "No summary available."), title="Reasoning", border_style="dim"))
                        else:
                            pass # run_nave_loop handled the panel
                    elif cmd == "/copilot":
                        copilot(args or Prompt.ask("Query"))
                    else: console.print(f"[red]Routing error for: {cmd}[/red]")
                
                elif res.get("type") == "shell":
                    cmd = res["command"]
                    if res.get("confirm", True):
                        console.print(Panel(f"[bold red]⚠️ EXECUTE SHELL COMMAND?[/bold red]\n\n[white]{cmd}[/white]", border_style="red"))
                        if Confirm.ask("Authorize?"):
                            from tools.shell import run_simple
                            console.print(run_simple(cmd))
                    else:
                        from tools.shell import run_simple
                        console.print(run_simple(cmd))
                
                else:
                    display_chat_message("User", res.get("args", text))
                    debug_loop(res.get("args", text))
            except EOFError:
                # Input stream closed in the middle of a command (piped stdin
                # exhausted, terminal closed): exit the REPL the same clean way
                # as EOF at the prompt instead of reporting a "System Error".
                break
            except KeyboardInterrupt:
                # Ctrl+C during a command cancels back to the prompt; the
                # double-press-to-exit logic at the prompt is unchanged.
                console.print("\n[yellow]Cancelled.[/yellow]")
                continue
            except Exception as e:
                entry = ErrorLogger.log_error(e, context=f"Command: {text}")
                console.print(f"[bold red]❌ System Error:[/bold red] {e}")
                if Confirm.ask("Initiate autonomous debug analysis?"):
                    ErrorLogger.auto_debug(f"Error: {e}\nStack: {entry['stack_trace']}")

        except KeyboardInterrupt:
            now = time.time()
            if now - last_ctrl_c < 2: 
                console.print("\n[yellow]Shutdown complete.[/yellow]"); break
            else:
                console.print("\n[bold red]Press Ctrl+C again to exit.[/bold red]")
                last_ctrl_c = now
        except EOFError: break

# (single callback defined above; duplicate removed)

def ollama_cli(args: str):
    """Pass-through CLI for Ollama."""
    import subprocess
    import os
    if not args:
        console.print("[yellow]Usage: /ollama [args][/yellow]")
        return
    
    from core.config import load_config
    cfg = load_config()
    host = cfg.get("ollama_host", "http://localhost:11434")
    env = os.environ.copy()
    env["OLLAMA_HOST"] = host
    
    import shlex
    cmd = ["ollama"] + shlex.split(args)
    console.print(f"[dim]Running: {' '.join(cmd)} (Host: {host})[/dim]")
    try:
        subprocess.run(cmd, env=env, shell=False)
    except FileNotFoundError:
        console.print("[red]❌ 'ollama' executable not found in PATH.[/red]")
    except Exception as e:
        console.print(f"[red]❌ Error executing ollama: {e}[/red]")

@app.command()
def ollama(args: str = typer.Argument(None, help="Arguments to pass to the ollama CLI")):
    """Pass-through CLI for Ollama."""
    ollama_cli(args)

@app.command()
def ollama_login():
    """Sign in to Ollama Cloud to enable cloud models."""
    from core.utils import open_url
    from core.config import load_config, save_config
    
    console.print("[bold cyan]Ollama Cloud Login[/bold cyan]")
    console.print("Opening Ollama website. Please log in and find your API token in your account settings/dashboard.")
    open_url("https://ollama.com")

    token = Prompt.ask("Enter your Ollama account token", password=True)
    if token:
        cfg = load_config()
        cfg["ollama_token"] = token
        cfg["ollama_cloud_host"] = "https://ollama.com/api"
        save_config(cfg)
        console.print("[bold green]✅ Ollama Cloud configured successfully![/bold green]")
        console.print("You can now use cloud models by adding '-cloud' to the model name.")

@app.command()
def setup(): setup_wizard()

@app.command()
def p2p_scan():
    """Scan local network for other JARVIS instances."""
    from core.p2p import scan_for_jarvis_peers
    console.print("[cyan]Searching for JARVIS peers on local network...[/cyan]")
    peers = scan_for_jarvis_peers()
    if not peers:
        console.print("[yellow]No other JARVIS instances found.[/yellow]")
    else:
        console.print(f"[green]Found JARVIS peers at: {', '.join(peers)}[/green]")

@app.command()
def p2p_status():
    """Scan and display a detailed report of all JARVIS peers on the network."""
    from core.p2p import p2p_status_report
    p2p_status_report()

@app.command()
def p2p_edit(peer_ip: str, path: str, old_string: str, new_string: str):
    """Request to edit a file on a remote JARVIS instance."""
    from core.p2p import send_remote_command
    console.print(f"[cyan]Requesting to edit '{path}' on {peer_ip}...[/cyan]")
    res = send_remote_command(peer_ip, "edit_file", {"path": path, "old_string": old_string, "new_string": new_string})
    if res["ok"]:
        console.print(f"[green]✅ {res['data']}[/green]")
    else:
        console.print(f"[red]❌ {res['error']}[/red]")

@app.command()
def p2p_set_token(token: str):
    """Set the P2P shared secret token for swarm trust."""
    from core.config import load_config, save_config
    cfg = load_config()
    cfg["p2p_token"] = token
    save_config(cfg)
    console.print(f"[green]✅ P2P Token set successfully.[/green]")

@app.command()
def p2p_read(peer_ip: str, path: str):
    """Request to read a file from a remote JARVIS instance."""
    from core.p2p import send_remote_command
    console.print(f"[cyan]Requesting to read '{path}' from {peer_ip}...[/cyan]")
    res = send_remote_command(peer_ip, "read_file", {"path": path})
    if res["ok"]:
        console.print(Panel(res["data"], title=f"File: {path} (from {peer_ip})"))
    else:
        console.print(f"[red]❌ {res['error']}[/red]")

@app.command()
def p2p_server():
    """Start the P2P server to allow remote requests."""
    from core.p2p import run_p2p_server
    run_p2p_server()

@app.command()
def p2p_tokens():
    """Interactive menu for discovering and requesting tokens from peers."""
    from core.p2p import p2p_token_menu
    p2p_token_menu()

@app.command()
def restart():
    console.print("[yellow]🔄 Restarting JARVIS...[/yellow]")
    os.execv(sys.executable, ['python3'] + sys.argv)

@app.command()
def reinstall():
    """Perform a clean sovereign reinstallation of the JARVIS ecosystem."""
    if Confirm.ask("[bold red]⚠️ DANGER: This will wipe your local installation and start fresh. Proceed?[/bold red]"):
        console.print("[bold yellow]🚀 Initiating Sovereign Reinstallation...[/bold yellow]")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        os.system(f"cd {base_dir} && bash install.sh")
        console.print("[bold green]✅ Reinstallation complete. Please restart JARVIS.[/bold green]")
        sys.exit(0)

@app.command()
def chat(q: str, 
         model: Annotated[Optional[str], typer.Option("--model", "-m")] = None, 
         prompt: Annotated[Optional[str], typer.Option("--prompt", "-p")] = None):
    display_chat_message("User", q)
    res = think_structured("", q, model=model, prompt_name=prompt)
    txt = process_think_res(res)
    if txt: console.print(Markdown(txt))

@app.command()
def fix(issue: str, model: Annotated[Optional[str], typer.Option("--model", "-m")] = None, prompt: Annotated[Optional[str], typer.Option("--prompt", "-p")] = None):
    display_chat_message("Fix Request", issue)
    debug_loop(issue, model=model, prompt=prompt)

@app.command()
def plan(task: str, model: Annotated[Optional[str], typer.Option("--model", "-m")] = None):
    from core.planning import save_plan, display_plan
    from core.agent import generate_plan
    
    display_chat_message("Strategy Phase", task)
    res = generate_plan(task, model=model)
    txt = process_think_res(res)
    
    if txt:
        plan_path = save_plan("active_plan", txt)
        display_plan("active_plan")
        
        if Confirm.ask("[bold yellow]Accept this plan and transition to Execution Mode?[/bold yellow]"):
            console.print("[green]✅ Plan approved. Execution initiated.[/green]")
            # Proceed to execution (forge loop or similar)
        else:
            console.print("[yellow]Plan rejected. Staying in Plan Mode.[/yellow]")
            # Logic to keep the CLI in a "Plan" sub-prompt loop would go here


@app.command()
def forge(task: str, model: Annotated[Optional[str], typer.Option("--model", "-m")] = None):
    display_chat_message("Forge Task", task)
    forge_loop(task, model=model)

@app.command()
def decode(content: str):
    res = think_structured("", f"Decode and explain with maximum depth: {content}")
    txt = process_think_res(res)
    if txt: console.print(Markdown(txt))

@app.command()
def lookup(request: str):
    res = think_structured("", f"Suggest best command for: {request}")
    txt = process_think_res(res)
    if txt: console.print(Panel(Markdown(txt), title="Lookup"))

@app.command()
def hardware_menu():
    from tools.hardware import get_hardware_summary, list_usb_devices, probe_ports
    while True:
        console.print(get_hardware_summary())
        console.print("\n[1] USB | [2] All Ports | [b] Back")
        c = Prompt.ask("Choice", choices=["1", "2", "b"], default="b")
        if c == "1": console.print(Panel(list_usb_devices()))
        elif c == "2": console.print(Panel(probe_ports()))
        else: break

@app.command()
def analyze_file(path: str, model: Annotated[Optional[str], typer.Option("--model", "-m")] = None, prompt: Annotated[Optional[str], typer.Option("--prompt", "-p")] = None):
    if not os.path.exists(path): console.print(f"[red]Error: Not found:[/red] {path}"); return
    with open(path, 'r') as f: content = f.read()
    console.print(f"[bold cyan]Auditing:[/bold cyan] {path}...")
    res = think_structured(f"Path: {path}\nContent:\n{content}", "Deep security and performance audit.", model=model, prompt_name=prompt)
    txt = process_think_res(res)
    if txt: console.print(Markdown(txt))

@app.command()
def locate(name: str, root: str = "/"):
    from tools.search import system_find
    console.print(f"[bold cyan]Searching for '{name}'...[/bold cyan]")
    console.print(Panel(system_find(name, root), title="Locate"))

@app.command()
def launch(tool: str):
    from tools.launcher import launch_tool
    console.print(f"[bold cyan]Launching:[/bold cyan] {tool}")
    console.print(f"[green]{launch_tool(tool)}[/green]")

def show_free_providers():
    """Show providers usable without an API key (local models) and their status."""
    from core.services import validate_ollama
    from core.config import load_config
    cfg = load_config()
    host = cfg.get("ollama_host", "http://localhost:11434")
    table = Table(title="Key-free providers", border_style="green")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="white")
    # Local providers that need no API key
    res = validate_ollama(host)
    ollama_ok = res.get("ok")
    table.add_row("ollama (local)", "[green]reachable[/green]" if ollama_ok else f"[red]not reachable at {host}[/red]")
    for name in ("llama_cpp", "gpt4all", "vllm", "sglang", "local"):
        table.add_row(name, "[dim]configure a local server, then select via /model[/dim]")
    console.print(table)
    console.print("[dim]Tip: use /model to switch providers, /doctor to repair Ollama.[/dim]")

@app.command()
def troubleshoot(command: str, model: Annotated[Optional[str], typer.Option("--model", "-m")] = None, prompt: Annotated[Optional[str], typer.Option("--prompt", "-p")] = None):
    troubleshoot_loop(command, model=model, prompt=prompt)

@app.command()
def undo(path: str):
    from tools.editor import undo_last_edit
    console.print(f"[green]{undo_last_edit(path)}[/green]")

@app.command()
def dashboard():
    from core.dashboard import Dashboard; Dashboard().run()

@app.command()
def focus(path: str):
    if os.path.exists(path): console.print(Panel(f"[green]Focus set:[/green] {os.path.abspath(path)}", border_style="green"))
    else: console.print(f"[red]Error: Missing path:[/red] {path}")

@app.command()
def voice():
    try:
        from voice.voice import run_voice
    except ImportError as e:
        console.print(f"[red]Voice support needs extra packages: {e}.[/red]")
        console.print("[dim]Install with: pip install sounddevice scipy SpeechRecognition[/dim]")
        return
    run_voice()

@app.command()
def watch():
    try:
        from watcher.monitor import start_monitor
    except ImportError as e:
        console.print(f"[red]Watcher needs the watchdog package: {e}.[/red]")
        console.print("[dim]Install with: pip install watchdog[/dim]")
        return
    start_monitor()

@app.command()
def config(): menus.config_menu()

@app.command()
def analyze(path: Annotated[str, typer.Argument(help="Path to analyze")] = "."):
    from tools.analytics import project_summary
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        if not os.path.exists(path):
            console.print(f"[bold red]Error:[/bold red] Path '[yellow]{path}[/yellow]' does not exist.")
            return
        s = project_summary(path)

    t = Table(title=f"Project Health: {path}", border_style="cyan")
    t.add_column("Metric", style="white"); t.add_column("Value", style="bold cyan")
    t.add_row("Total Files", str(s["total_files"])); t.add_row("Total Lines", str(s["total_lines"]))
    lang_str = ", ".join([f"{k}: {v}" for k, v in sorted(s["languages"].items(), key=lambda x: x[1], reverse=True)[:3]])
    t.add_row("Top Languages", lang_str)
    console.print(t)
    if s["hotspots"]:
        h_table = Table(title="Complexity Hotspots (Refactor Recommended)", border_style="red")
        h_table.add_column("Path", style="white"); h_table.add_column("Score", style="bold red")
        for h in sorted(s["hotspots"], key=lambda x: x["score"], reverse=True)[:5]:
            h_table.add_row(h["path"], str(h["score"]))
        console.print(h_table)

@app.command()
def run_doctor():
    from core.deps import ensure_all; ensure_all()
    display_health_report(check_system_health())

@app.command()
def ai_git(task: str):
    res = think_structured("", f"Git task: {task}")
    txt = process_think_res(res)
    if txt: console.print(Markdown(txt))

@app.command()
def copilot(query: str, action: Annotated[str, typer.Option("--action", "-a")] = "suggest"):
    from tools.copilot import copilot_suggest, copilot_explain
    if action == "suggest": res = copilot_suggest(query)
    else: res = copilot_explain(query)
    console.print(Panel(res, title=f"GitHub Copilot ({action.capitalize()})", border_style="cyan"))

@app.command()
def box_menu(args: str = ""):
    tokens = args.split()
    if not tokens:
        console.print("[bold cyan]Gemini Multi-Box Engine[/bold cyan]")
        boxes = gemini_session.list_boxes()
        if not boxes: console.print("[dim]No active boxes.[/dim]")
        else:
            t = Table(title="Active Boxes", border_style="cyan")
            t.add_column("Box Name"); t.add_column("Last CMD Status")
            for b in boxes:
                logs = gemini_session.show_box_output(b)
                status = f"[green]Success[/green]" if logs and logs[-1]["returncode"] == 0 else f"[red]Error ({logs[-1]['returncode']})[/red]" if logs else "[dim]Idle[/dim]"
                t.add_row(b, status)
            console.print(t)
        console.print("\nUsage: /box create [name] | /box run [name] [cmd] | /box tail [name]")
        return
    sub = tokens[0]
    if sub == "create" and len(tokens) > 1:
        name = tokens[1]
        if gemini_session.create_box(name): console.print(f"[green]Box '{name}' initialized.[/green]")
        else: console.print(f"[red]Box '{name}' already exists.[/red]")
    elif sub == "run" and len(tokens) > 2:
        name = tokens[1]; cmd = " ".join(tokens[2:])
        res = gemini_session.run_in_box(name, cmd)
        if res["ok"]: console.print(Panel(res["stdout"] or "[dim]No output[/dim]", title=f"Box '{name}' Output", border_style="green"))
        else:
            console.print(f"[red]Execution failed in box '{name}': {res.get('error')}[/red]")
            if res.get("stderr"): console.print(Panel(res["stderr"], title="Error Log", border_style="red"))
    elif sub == "tail" and len(tokens) > 1:
        name = tokens[1]; console.print(Panel(gemini_session.tail_box(name), title=f"Tail: {name}", border_style="dim"))
    elif sub == "close" and len(tokens) > 1:
        name = tokens[1]
        if gemini_session.close_box(name): console.print(f"[yellow]Box '{name}' closed.[/yellow]")

@app.command()
def examine_py(path: str):
    from tools.python_agent import file_summary
    if not os.path.exists(path):
        console.print(f"[red]Error: File not found: {path}[/red]"); return
    console.print(Panel(file_summary(path), title=f"Examination: {path}", border_style="cyan"))

@app.command()
def patch_py(path: str, instruction: str = ""):
    from tools.python_agent import suggest_patch_via_llm, safe_apply_new_content
    if not os.path.exists(path):
        console.print(f"[red]Error: File not found: {path}[/red]"); return
    if not instruction: instruction = Prompt.ask("Instruction for patch")
    with console.status(f"[bold yellow]Analyzing and generating patch for {path}..."):
        res = suggest_patch_via_llm(path, instruction)
    if not res["ok"]:
        console.print(f"[red]Patch Error: {res.get('error')}[/red]"); return
    console.print(Panel(res["unified_diff"], title="Suggested Patch (Unified Diff)", border_style="yellow"))
    if Confirm.ask("Apply this patch?"):
        ok, msg = safe_apply_new_content(path, res["suggested"])
        if ok: console.print(f"[bold green]{msg}[/bold green]")
        else: console.print(f"[bold red]Failed to apply: {msg}[/bold red]")
    else: console.print("[yellow]Patch aborted by user.[/yellow]")

@app.command()
def init():
    if os.path.exists("JARVIS.md"): console.print("[yellow]Exists.[/yellow]")
    else:
        with open("JARVIS.md", "w") as f: f.write("# JARVIS Rules")
        console.print("[green]Created.[/green]")

def show_model_status():
    p_obj = get_provider(); p_name = get_env_with_config("provider") or "ollama"
    console.print(Panel(f"Brain: {p_name.upper()}\nModel: {p_obj.model}", title="Status", border_style="magenta"))

@app.command()
def brain():
    """Switch LLM brain (provider) via interactive menu."""
    menus.models_menu()

@app.command()
def model(name: Optional[str] = None):
    """Switch LLM model for the current brain."""
    models_command(name)

def models_command(name: Optional[str] = None):
    config = load_config()
    provider = config.get("provider", "ollama")
    tier = config.get("machine_tier", "medium")
    
    # Advanced Model & Tool Mapping
    # Providers/models here must have real support in core.services.
    model_map = {
        "ollama": ["llama3.3", "llama3.2", "phi4", "qwen3", "deepseek-r1"],
        "openai": ["gpt-4o", "gpt-4o-mini", "o1-preview", "o1-mini"],
        "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-sonnet-20240620",
                      "claude-3-opus-20240229"],
        "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "mistral": ["mistral-large-latest", "mistral-medium-latest"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "groq": ["llama-3.3-70b-versatile"],
        "together": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-72B-Instruct"],
        "cohere": ["command-r-plus", "command-r"],
        "perplexity": ["llama-3.1-sonar-large-128k-online"],
        "qwen": ["qwen3", "qwen2.5"],
        "gpt4all": ["default"],
        "llama_cpp": ["local-model"],
        "vllm": ["meta-llama/Meta-Llama-3-70B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "sglang": ["meta-llama/Meta-Llama-3-8B-Instruct"],
        "nemotron": ["default"],
        "local": ["default"],
    }

    # Must match tools.launcher.TOOL_REGISTRY — entries here launch for real.
    ai_tools = {
        "claude-desktop": "Anthropic's official desktop client",
        "claude": "Anthropic's Claude Code (with subagents)",
        "hermes": "Nous Research Hermes Agent",
        "openclaw": "OpenClaw Personal AI",
        "opencode": "OpenCode terminal agent",
        "copilot": "GitHub Copilot CLI",
        "aider": "High-speed CLI pair programming agent",
        "droid": "Factory's coding agent",
        "pi": "Minimal AI agent toolkit",
        "pool": "Poolside's coding agent",
        "codex": "OpenAI's open-source coding agent",
        "interpreter": "Open Interpreter",
        "gpt-engineer": "GPT Engineer",
        "mentat": "Mentat coding assistant",
    }

    if name:
        if name in ai_tools:
            launch(tool=name)
            return
        
        # Support for -cloud suffix logic
        config["jarvis_model"] = name
        save_config(config)
        
        if name.endswith("-cloud"):
            console.print(f"[green]✅ Model switched to Cloud: {name}[/green]")
            console.print("[dim]Requests will be routed to https://ollama.com/api with your bearer token.[/dim]")
        else:
            console.print(f"[green]✅ Model switched to: {name}[/green]")
        return

    # Generate Status Table
    from core.services import get_api_key
    status_table = Table(title="Intelligence Provider Status", border_style="dim")
    status_table.add_column("Provider", style="cyan")
    status_table.add_column("Status", justify="center")
    status_table.add_column("Provider", style="cyan")
    status_table.add_column("Status", justify="center")
    status_table.add_column("Provider", style="cyan")
    status_table.add_column("Status", justify="center")

    from core.services import KNOWN_PROVIDERS
    all_providers = KNOWN_PROVIDERS

    rows = []
    for i in range(0, len(all_providers), 3):
        row = []
        for j in range(3):
            if i + j < len(all_providers):
                p = all_providers[i+j]
                is_linked = False
                if p in ["ollama", "vllm", "sglang", "llama_cpp", "gpt4all", "nemotron", "qwen", "local"]:
                    is_linked = config.get(f"{p}_host") is not None
                else:
                    is_linked = get_api_key(p) is not None
                status = "[bold green]✓[/bold green]" if is_linked else "[bold red]✘[/bold red]"
                row.extend([p.upper(), status])
            else:
                row.extend(["", ""])
        rows.append(row)

    for r in rows: status_table.add_row(*r)
    console.print(status_table)

    console.print("\n[bold cyan]Intelligence Control Center[/bold cyan]")
    console.print("[1] Switch Models (Current Provider)")
    console.print("[2] Launch AI Tools (Specialized Agents)")
    console.print("[b] Back")

    top_choice = Prompt.ask("Select category", choices=["1", "2", "b"], default="1")
    
    if top_choice == "1":
        _provider_key = provider.lower()
        if _provider_key == "claude":
            _provider_key = "anthropic"  # legacy config value
        options = model_map.get(_provider_key, ["llama3"])
        
        # Hardware Tiering Filter
        if tier == "low" and provider == "ollama":
            console.print("[yellow]⚠️ Low-end hardware detected. Heavy local models hidden.[/yellow]")
            options = [m for m in options if "70b" not in m and "dbrx" not in m]

        console.print(f"\n[bold white]Models for {provider.upper()} ({tier.upper()} TIER):[/bold white]")
        for i, m in enumerate(options):
            console.print(f"[{i+1}] {m}")
        
        choice = Prompt.ask("Choice", choices=[str(i+1) for i in range(len(options))] + ["b"], default="1")
        if choice != "b":
            selected = options[int(choice)-1]
            config["jarvis_model"] = selected
            save_config(config)
            console.print(f"[green]✅ Now using {selected}[/green]")
            
    elif top_choice == "2":
        t_list = list(ai_tools.keys())
        console.print("\n[bold white]Specialized AI Tools:[/bold white]")
        for i, t in enumerate(t_list):
            console.print(f"[{i+1}] {t} - [dim]{ai_tools[t]}[/dim]")
        
        choice = Prompt.ask("Choice", choices=[str(i+1) for i in range(len(t_list))] + ["b"], default="1")
        if choice != "b":
            selected = t_list[int(choice)-1]
            launch(tool=selected)

@app.command()
def update():
    from core.update import manual_upgrade; manual_upgrade()

@app.command()
def upgrade():
    from core.update import manual_upgrade; manual_upgrade()

@app.command()
def sync():
    from core.health import update_all_repos; update_all_repos()

@app.command()
def repair_ollama_cmd(host: Optional[str] = None):
    """Attempt to repair or reconfigure Ollama automatically."""
    console.print("[bold cyan]Repairing Ollama...[/bold cyan]")
    report = repair_ollama(host=host)
    t = Table(title="Ollama Repair Report")
    t.add_column("Key"); t.add_column("Value")
    t.add_row("Fixed", str(report.get("fixed")))
    t.add_row("Details", "\n".join(report.get("details", [])[:10]))
    attempts = report.get("attempts", [])
    if attempts: t.add_row("Attempts", "\n".join([str(a) for a in attempts[:6]]))
    console.print(t)

@app.command()
def config_maintain():
    """Run one-off auto-config maintenance."""
    console.print("[cyan]Running one-off config maintenance...[/cyan]")
    r = auto_config_maintenance_once()
    console.print(Panel(json.dumps(r, indent=2), title="Config Maintenance"))

@app.command()
def start_config_maintenance(interval_hours: int = 24):
    """Start background periodic config maintenance."""
    start_periodic_config_maintenance(interval_hours=interval_hours)
    console.print(f"[green]Started periodic config maintenance every {interval_hours} hours.[/green]")

@app.command()
def connect_provider(provider: str, host: Optional[str] = None, key: Optional[str] = None):
    """Connect and configure a provider (delegates to the easy-connect module)."""
    from core.connect import connect_provider_cli
    connect_provider_cli(provider, host=host, key=key)

@app.command()
def connections(test: bool = typer.Option(False, "--test", help="Probe reachability of each configured provider")):
    """Show a connection-status table for all AI providers. Keys are never printed."""
    from core.connect import connection_status, render_status_table
    rows = connection_status(test=test)
    console.print(render_status_table(rows))

@app.command()
def webask(query: str, provider: Optional[str] = None):
    """Perplexity-like web assistant: search web and synthesize answer with citations."""
    from core.perplexity_like import bing_search, extract_search_snippets, synthesize_answer
    console.print(f"[dim]Searching web for:[/dim] {query}")
    s = bing_search(query)
    if not s.get("ok"):
        console.print(f"[red]Search failed: {s.get('error')}[/red]"); return
    snippets = extract_search_snippets(s["raw"])
    res = synthesize_answer(query, snippets, provider=provider)
    if not res.get("ok"):
        console.print(f"[red]Summarization failed: {res.get('error')}[/red]"); return
    console.print(Panel(res["answer"], title=f"Answer ({res.get('provider')}/{res.get('model')})", border_style="cyan"))
    if res["sources"]:
        console.print(Panel("\n".join(res["sources"]), title="Sources", border_style="magenta"))

@app.command()
def optimize():
    """Optimize JARVIS and system environment for peak performance."""
    from core.deps import ensure_all
    import shutil
    
    console.print("[bold cyan]🚀 Starting Optimization Suite...[/bold cyan]")
    
    # 1. Clear __pycache__
    console.print("[dim]Cleaning Python bytecode cache...[/dim]")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, files in os.walk(base_dir):
        if "__pycache__" in dirs:
            shutil.rmtree(os.path.join(root, "__pycache__"))
    
    # 2. Refresh Dependency Cache
    console.print("[dim]Refreshing dependency status...[/dim]")
    ensure_all(force=True)
    
    # 3. System Cleanup Suggestions (Info only)
    if sys.platform == "darwin":
        if shutil.which("brew"):
            console.print("[dim]Note: Run 'brew upgrade' to keep system tools updated.[/dim]")
    elif shutil.which("apt"):
        console.print("[dim]Note: Run 'sudo apt update && sudo apt upgrade' to keep system tools updated.[/dim]")

    console.print("[bold green]✅ Optimization complete![/bold green]")

if __name__ == "__main__": app()
