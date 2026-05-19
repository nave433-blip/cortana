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
        "qwen": "Get an API key at https://dashscope.console.aliyun.com",
        "anthropic": "Get an API key at https://console.anthropic.com",
        "mistral": "Get an API key at https://console.mistral.ai",
        "kimi": "Get an API key at https://platform.moonshot.cn",
        "perplexity": "Get an API key at https://www.perplexity.ai/settings/api",
        "granite": "Get an API key at https://www.ibm.com/granite",
        "nemotron": "Get an API key at https://build.nvidia.com"
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
            # Prompt for all defined providers
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
            
            # Ensure required models exist
            for model in ["tinyllama", "alpaca"]:
                if model not in "".join(models).lower():
                    console.print(f"[yellow]⚠️ Required model '{model}' missing.[/yellow]")
                    svc.install_ollama_model(model)
                    
            if 'gemma4:latest' in models or 'gemma' in ''.join(models).lower(): console.print("[dim][green]✓ Gemma4 Detected.[/green][/dim]")
            if 'qwen2.5:latest' in models or 'qwen' in ''.join(models).lower(): console.print("[dim][green]✓ Qwen Detected.[/green][/dim]")
            
        # Check cloud dependencies
        svc.check_cloud_dependencies()
    except Exception as e:
        console.print(f"[dim]Auto-detect models failed: {e}[/dim]")

    # 2.5 Hardware check
    try:
        from tools.hardware import check_system_specs
        specs = check_system_specs()
        if specs.get("is_low_end"):
            console.print(Panel(f"Detected RAM: {specs.get('ram_gb', 'Unknown')}GB | GPU: {'Yes' if specs.get('has_gpu') else 'No'}", title="Low-End Hardware Detected", border_style="yellow"))
    except Exception:
        specs = {}

    # 3. Check Cloud Ollama
    if not cfg.get("ollama_token"):
        prompt_text = "⚠️ [bold cyan]Ollama Cloud[/bold cyan] is not configured. Sign in to your account to enable cloud models?"
        if specs.get("is_low_end"):
            prompt_text = "⚠️ [yellow]Low-end hardware detected.[/yellow] Sign in to [bold cyan]Ollama Cloud[/bold cyan] for better performance?"
            
        if not auto and Confirm.ask(prompt_text):
            from core.utils import open_url
            console.print("[dim]Opening Ollama website. Please log in and find your API token in your account settings/dashboard.[/dim]")
            open_url("https://ollama.com")
            token = Prompt.ask("Enter your Ollama account token", password=True)
            if token:
                cfg["ollama_token"] = token
                cfg["ollama_cloud_host"] = "https://ollama.com/api"
                save_config(cfg)
                console.print("[green]✅ Ollama Cloud configured successfully.[/green]")
    elif not cfg.get("ollama_cloud_host"):
        cfg["ollama_cloud_host"] = "https://ollama.com/api"
        save_config(cfg)
        console.print("[dim]Auto-set Ollama Cloud API URL.[/dim]")

    # 4. Check P2P Connectivity
    if not cfg.get("p2p_enabled"):
        if not auto and Confirm.ask("⚠️ [bold cyan]P2P Features[/bold cyan] (Local Network Peer-to-Peer) are not configured. Enable them now?"):
            cfg["p2p_enabled"] = True
            cfg["p2p_share_keys"] = Confirm.ask("Do you want to enable sharing API keys across P2P?")
            cfg["p2p_share_fs"] = Confirm.ask("Do you want to enable file system edits via P2P?")
            cfg["p2p_share_tokens"] = Confirm.ask("Do you want to enable sharing login tokens across P2P?")
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
            
            # Register for global P2P if enabled
            if cfg.get("global_p2p_enabled"):
                from core.global_p2p import register_node
                register_node()
                
            from tools.p2p_monitor import start_monitor
            start_monitor()
                
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
