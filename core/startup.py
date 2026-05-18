from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
import core.services as svc
from core.config import load_config, save_config
from tools.network import scan_network_for_ollama
import os

console = Console()
DEFAULT_PROVIDERS = ["ollama", "openai", "gemini", "anthropic", "mistral", "deepseek", "qwen", "kimi", "perplexity", "granite", "nemotron", "groq", "together"]

def _interactive_connect(provider: str) -> Dict[str, Any]:
    provider = provider.lower()
    result = {"provider": provider, "connected": False, "message": ""}
    FREE_GUIDE = {
        "groq": "Get a free API key at https://groq.com",
        "together": "Get a free API key at https://together.ai",
        "deepseek": "Get an API key at https://platform.deepseek.com",
        "qwen": "Get an API key at https://dashscope.console.aliyun.com"
    }
    try:
        if provider == "ollama":
            host = Prompt.ask("Enter Ollama host", default="http://localhost:11434")
            cfg = load_config()
            cfg["ollama_host"] = host
            save_config(cfg)
            result.update({"connected": True, "message": f"Ollama host updated to {host}"})
            return result
        
        if provider in FREE_GUIDE:
            console.print(Panel(FREE_GUIDE[provider], title=f"{provider.upper()} Guide", border_style="green"))
            
        key = Prompt.ask(f"Enter {provider.upper()} API key", password=True)
        if key:
            svc.set_api_key(provider, key)
            result.update({"connected": True, "message": f"{provider.upper()} key saved."})
        return result
    except Exception as e:
        return {"connected": False, "message": f"Connect failed: {e}"}

def check_provider(provider: str, auto: bool = False) -> Dict[str, Any]:
    status = {"provider": provider, "ok": False, "validated": False, "action_taken": None, "message": None}
    try:
        v = svc.validate_provider_connection(provider)
        status["ok"] = v.get("ok", False)
        status["validated"] = v.get("ok", False)
        status["message"] = v.get("error") or v.get("note") or "Connected" if v.get("ok") else "Missing configuration"
        
        if not status["ok"] and not auto:
            # Only prompt for core providers
            CORE_PROVIDERS = ["ollama", "openai", "gemini", "groq"]
            if provider in CORE_PROVIDERS:
                if Confirm.ask(f"⚠️ Provider [bold cyan]'{provider.upper()}'[/bold cyan] is not ready. Configure it now?"):
                    conn = _interactive_connect(provider)
                    if conn.get("connected"):
                        status["ok"] = True
                        status["message"] = conn.get("message")
    except Exception as e:
        status["ok"] = False
        status["message"] = str(e)
    return status

def startup_check_and_login(auto: bool = False, providers: Optional[List[str]] = None, start_maintenance: bool = True) -> Dict[str, Any]:
    # 1. Auto-scan network for Ollama
    console.print("[dim]Scanning network for Ollama instances...[/dim]")
    found_hosts = scan_network_for_ollama()
    cfg = load_config()
    if found_hosts:
        hosts = cfg.get("ollama_hosts", ["http://localhost:11434"])
        new_hosts = list(set(hosts + found_hosts))
        if len(new_hosts) > len(hosts):
            cfg["ollama_hosts"] = new_hosts
            save_config(cfg)
            console.print(f"[green]✅ Distributed compute ready. Discovered: {', '.join(found_hosts)}[/green]")
        
    # 2. Proactively detect local models
    try:
        console.print("[dim]Detecting available Ollama models...[/dim]")
        res = svc.list_models_for_provider("ollama")
        if res.get("ok"):
            models = res.get("models", [])
            cfg["detected_local_models"] = models
            save_config(cfg)
            if 'gemma4:latest' in models or 'gemma' in ''.join(models).lower(): console.print("[dim][green]✓ Gemma4 Detected.[/green][/dim]")
            if 'qwen2.5:latest' in models or 'qwen' in ''.join(models).lower(): console.print("[dim][green]✓ Qwen Detected.[/green][/dim]")
    except Exception as e:
        console.print(f"[dim]Auto-detect models failed: {e}[/dim]")

    # 3. Check Cloud Ollama
    if not cfg.get("ollama_cloud_host"):
        if not auto and Confirm.ask("⚠️ No [bold cyan]Cloud Ollama[/bold cyan] host configured. Set one up for high-availability fallback?"):
            host = Prompt.ask("Enter Cloud Ollama URL", default="https://your-remote-ollama.com")
            if host:
                cfg["ollama_cloud_host"] = host
                save_config(cfg)
                console.print(f"[green]✅ Cloud Ollama host saved: {host}[/green]")

    # 4. Check P2P Connectivity
    if not cfg.get("p2p_enabled"):
        if not auto and Confirm.ask("⚠️ [bold cyan]P2P Features[/bold cyan] (Local Network Peer-to-Peer) are not configured. Enable them now?"):
            cfg["p2p_enabled"] = True
            save_config(cfg)
            console.print("[green]✅ P2P Features enabled.[/green]")
        else:
            cfg["p2p_enabled"] = False
            save_config(cfg)

    # 5. Connectivity initialization
    report = {"auto": bool(auto), "results": [], "maintenance_started": False}
    provs = providers or DEFAULT_PROVIDERS

    # Start P2P Server in background if enabled
    if cfg.get("p2p_enabled"):
        try:
            from core.p2p import start_server_background
            start_server_background()
            console.print("[dim][green]✓ P2P Server Online[/green][/dim]")
        except Exception as e:
            console.print(f"[dim][red]! P2P Server failed: {e}[/red][/dim]")

    console.print(Panel(f"JARVIS System Initialization: Verifying connectivity to {len(provs)} providers...", title="Startup", border_style="cyan"))

    
    for p in provs:
        res = check_provider(p, auto=auto)
        report["results"].append(res)
        if res.get("ok"):
            console.print(f"  [green]✓[/green] {p.upper()}: [dim]{res.get('message')}[/dim]")
        else:
            # For non-core providers, just a dim warning if missing
            console.print(f"  [yellow]![/yellow] {p.upper()}: [dim]{res.get('message')}[/dim]")

    if start_maintenance:
        try:
            from core.config import start_auto_maintenance
            start_auto_maintenance(interval_hours=24)
            report["maintenance_started"] = True
        except: pass

    console.print(Panel("Intelligence core online. Systems nominal.", title="Status", border_style="green"))
    return report
