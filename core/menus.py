import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.markdown import Markdown
from core.config import load_config, save_config, setup_wizard

console = Console()

def config_menu():
    """Manage global JARVIS settings, identities, and API keys with detailed guidance."""
    while True:
        config_data = load_config()
        table = Table(title="[bold cyan]Global System Configuration Control[/bold cyan]", show_header=True, header_style="bold magenta")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Functional Description", style="dim")
        
        descriptions = {
            "provider": "The primary LLM engine. Options include local Ollama, or high-performance cloud providers like Gemini, OpenAI, and Claude.",
            "jarvis_model": "The specific model identifier (e.g., 'gpt-4o' or 'llama3'). This string is passed directly to the active provider's API.",
            "personality": "Controls the assistant's tone, verbosity, and interaction style. Affects both chat and autonomous agent responses.",
            "active_prompt": "Your persistent system persona. This role is loaded from your Prompt Library and guides all high-level technical reasoning.",
            "github_token": "Enables JARVIS to autonomously push code, open Pull Requests, manage issues, and sync with your repositories.",
            "gemini_api_key": "Token for Google Gemini. Recommended for free users (1,500 req/day) seeking professional-grade reasoning.",
            "openai_api_key": "Token for OpenAI GPT series. Industry standard for technical logic and sophisticated code synthesis.",
            "anthropic_api_key": "Token for Claude 3.5. Renowned for world-class coding ability and accurate follow-through on complex tasks.",
            "nvidia_api_key": "Token for NVIDIA NIM. Provides access to massive open-source models like Llama 3.1 405B on optimized hardware.",
            "xai_api_key": "Token for xAI Grok-Beta. Focused on technical truth, edge-case detection, and witty interaction.",
            "mistral_api_key": "Token for Mistral AI. Excellent performance-to-cost ratio for technical audits and multilingual decoding.",
            "ollama_host": "The URL where your local Ollama server is running. JARVIS will auto-detect this during setup if you're unsure.",
            "lm_studio_host": "The URL for your local LM Studio server. Enables use of any GGUF model as the assistant's brain.",
            "llama_cpp_host": "The URL for a Llama.cpp server instance. Optimized for low-level performance on specific hardware.",
            "gpt4all_host": "The URL for the local GPT4All API. Another layer of free, private, and offline intelligence support.",
            "model_mode": "Switch between 'manual', 'auto-offline' (Local Only), 'auto-online' (Cloud Priority), or 'auto-mixed' (Connectivity-aware).",
            "self_repair": "When ENABLED, JARVIS will autonomously attempt to patch its own source code if it crashes or hits a critical runtime error."
        }
        
        for k, v in config_data.items():
            val = v if "api_key" not in k and "token" not in k or not v else "🔒 ****" + v[-4:]
            desc = descriptions.get(k, "General system parameter controlling core behavioral logic.")
            table.add_row(k, str(val), desc)
        
        console.print(table)
        console.print("\n[bold white]Command Options:[/bold white]")
        console.print("[w] Launch Setup Wizard - Full step-by-step configuration for beginners.")
        console.print("[e] Edit Single Key     - Direct injection of one setting (e.g. updating an API key).")
        console.print("[b] Back                - Return to the previous menu.")
        
        choice = Prompt.ask("\nSelect action", choices=["w", "e", "b"], default="b")
        if choice == "w":
            setup_wizard()
        elif choice == "e":
            key = Prompt.ask("Enter the exact key name to edit")
            if key in config_data:
                val = Prompt.ask(f"Enter new value for {key}", default=str(config_data[key]))
                config_data[key] = val
                save_config(config_data)
                console.print(f"[green]✅ Successfully updated {key}. Settings are now live.[/green]")
            else:
                console.print(f"[red]❌ Error: Key '{key}' not recognized in system configuration.[/red]")
        else:
            break

def network_menu():
    """Advanced networking and discovery suite with detailed tool output."""
    from tools.network import scan_network, scan_ports
    while True:
        info_panel = """
        [bold cyan]Network & Connectivity Suite[/bold cyan]
        
        [1] [bold white]Subnet Discovery (Fing-style):[/bold white]
            Scans your local network to map out every active IP address and hostname. 
            Useful for finding local LLM servers or shared storage devices.
        
        [2] [bold white]Port Analytics (IP Scanner):[/bold white]
            Probes a target IP for open TCP ports (e.g. 11434 for Ollama, 22 for SSH).
            Essential for debugging server connections and remote accessibility.
            
        [b] Back to Main Menu
        """
        console.print(Panel(info_panel, title="DevOps: Networking", border_style="cyan"))
        choice = Prompt.ask("Select tool", choices=["1", "2", "b"], default="b")
        if choice == "1":
            console.print(scan_network())
            input("\nScan complete. Press Enter to continue...")
        elif choice == "2":
            ip = Prompt.ask("Target IP Address")
            ports = scan_ports(ip)
            if ports:
                console.print(f"[green]✅ Found {len(ports)} open ports on {ip}:[/green] {ports}")
            else:
                console.print(f"[yellow]⚠️ No open ports detected on {ip} within the standard range.[/yellow]")
            input("\nPress Enter to continue...")
        else: break

def server_menu():
    """Real-time system health and process management dashboard."""
    from tools.server import list_listening_ports, get_process_stats, kill_process
    while True:
        stats = get_process_stats()
        status = f"CPU Load: [bold]{stats['cpu_usage']}%[/bold] | RAM Usage: [bold]{stats['memory_usage']}%[/bold] | Active PIDs: [bold]{stats['process_count']}[/bold]"
        console.print(Panel(status, title="Node Health Status", border_style="green"))
        
        console.print("\n[bold white]Process Controls:[/bold white]")
        console.print("[1] List Port Map - Identify which services are occupying which network ports.")
        console.print("[2] Terminate Task - Force shutdown a process by its PID to free up system resources.")
        console.print("[b] Back           - Return to the previous menu.")
        
        choice = Prompt.ask("Select action", choices=["1", "2", "b"], default="b")
        if choice == "1":
            console.print(list_listening_ports())
            input("\nEnter to continue...")
        elif choice == "2":
            pid = Prompt.ask("Enter the PID to terminate")
            try:
                console.print(f"[yellow]{kill_process(int(pid))}[/yellow]")
            except: console.print("[red]Invalid PID format.[/red]")
        else: break

def memory_menu():
    """Vector database management for long-term assistant knowledge."""
    from memory.vector import get_stats, search, clear
    from rich.prompt import Confirm
    while True:
        stats = get_stats()
        mem_info = f"""
        [bold cyan]Neural Knowledge Base (FAISS)[/bold cyan]
        Stored Insights: [bold white]{stats['count']}[/bold white]
        
        [1] Search Brain - Query past conversations and technical insights by semantic meaning.
        [2] Wipe Database - Erase all stored context and start fresh with a clean slate.
        [b] Back         - Exit memory management.
        """
        console.print(Panel(mem_info, title="Core Memory", border_style="magenta"))
        choice = Prompt.ask("Choice", choices=["1", "2", "b"], default="b")
        if choice == "1":
            q = Prompt.ask("Semantic search query")
            results = search(q)
            if results: 
                console.print(Panel("\n".join([f"→ {r}" for r in results]), title=f"Relevant Insights: {q}"))
            else: 
                console.print("[yellow]⚠️ No relevant insights found in existing vector storage.[/yellow]")
            input("\nPress Enter to continue...")
        elif choice == "2":
            if Confirm.ask("[bold red]DANGER: Are you sure you want to permanently erase all JARVIS memories?[/bold red]"):
                console.print(f"[green]✅ {clear()}[/green]")
        else: break

def personality_menu():
    """Behavioral profile configuration for AI interaction style."""
    config = load_config()
    current = config.get("personality", "professional")
    
    info = """
    [bold white]Persona Selection Suite[/bold white]
    
    [1] [bold cyan]Professional:[/bold cyan] Precise, formal senior engineer. Prioritizes technical standards.
    [2] [bold cyan]Sarcastic:[/bold cyan] Grok-style edgy wit. Technical fixes served with a side of attitude.
    [3] [bold cyan]Concise:[/bold cyan] Minimalist. Provides the shortest possible correct technical answer.
    [4] [bold cyan]Mentor:[/bold cyan] Patient teacher. Explains the 'why' and encourages best practices.
    [5] [bold cyan]Nave-AI:[/bold cyan] Sovereign Integrator. High-precision multi-model refinement engine.
    """
    console.print(Panel(info, title=f"Current: {current.upper()}", border_style="cyan"))
    choice = Prompt.ask("Select personality", choices=["1", "2", "3", "4", "5", "b"], default="b")
    
    mapping = {"1": "professional", "2": "sarcastic", "3": "concise", "4": "mentor", "5": "nave_ai"}
    if choice in mapping:
        config["personality"] = mapping[choice]
        save_config(config)
        console.print(f"[green]✅ Identity updated. Your assistant is now operating in {mapping[choice].capitalize()} mode.[/green]")

def models_menu():
    """Intelligent orchestration and manual selection of LLM providers."""
    from core.services import get_api_key, validate_provider_connection
    config = load_config()
    current_p = config.get("provider", "ollama")
    current_m = config.get("jarvis_model", "llama3")
    current_mode = config.get("model_mode", "manual")
    
    header = f"""
    Mode: [bold green]{current_mode.upper()}[/bold green]
    Active Brain: [bold cyan]{current_p.upper()}[/bold cyan]
    Intelligence Model: [bold yellow]{current_m}[/bold yellow]
    """
    console.print(Panel(header, title="LLM Intelligence & Routing", border_style="magenta"))
    
    modes_info = """
    [bold white]Operation Modes:[/bold white]
    [a] Auto-Offline - Automatically find and use the best local runner (Ollama, LM Studio).
    [s] Auto-Online  - Prioritize world-class cloud models (Gemini Flash, GPT-4o).
    [x] Auto-Mixed   - Smart routing. Uses Cloud when online, pivots to Local when offline.
    [m] Manual Select - Override all automation and pick a specific provider below.
    """
    console.print(modes_info)

    specialties = Table(title="Model Specialties", show_header=True, header_style="bold magenta")
    specialties.add_column("Model/Provider", style="cyan")
    specialties.add_column("Specialty", style="white")
    specialties.add_row("DeepSeek R1/V3", "High-reasoning, complex logic, mathematics")
    specialties.add_row("Qwen2.5 72B", "Top-tier coding, multilingual, large context")
    specialties.add_row("Llama 3.3 70B", "General-purpose power, creative writing")
    specialties.add_row("GPT-4o / Mini", "Reliable logic, instruction following, versatility")
    specialties.add_row("Claude 3.5 Sonnet", "Nuanced reasoning, coding, professional tone")
    specialties.add_row("Gemini 2.0 Flash", "Fast, multimodal, web-connected research")
    console.print(specialties)

    p_mapping = {

        "1": "ollama", "2": "openai", "3": "gemini", "4": "claude", "5": "cohere", 
        "6": "mistral", "7": "nvidia", "8": "glm", "9": "deepseek", "0": "qwen",
        "g": "gemma", "k": "kimi", "p": "perplexity", "r": "granite", "l": "laguna",
        "v": "vllm", "y": "sglang", "f": "lfm", "e": "essential", "o": "olmo",
        "c": "cogito", "i": "minimax", "s": "stability", "u": "upstage", "z": "groq",
        "x": "xiaomi", "t": "tencent", "q": "kwaipilot"
    }

    # Generate Status Table
    status_table = Table(title="Intelligence Provider Status", border_style="dim")
    status_table.add_column("Key", style="cyan", justify="center")
    status_table.add_column("Provider", style="white")
    status_table.add_column("Status", justify="center")
    status_table.add_column("Key", style="cyan", justify="center")
    status_table.add_column("Provider", style="white")
    status_table.add_column("Status", justify="center")

    keys = list(p_mapping.keys())
    for i in range(0, len(keys), 2):
        row = []
        # Col 1
        k1 = keys[i]
        p1 = p_mapping[k1]
        is_linked1 = False
        if p1 in ["ollama", "vllm", "sglang", "laguna", "llama_cpp", "gpt4all", "local"]:
            is_linked1 = config.get(f"{p1}_host") is not None
        else:
            is_linked1 = get_api_key(p1) is not None
        status1 = "[bold green]✓[/bold green]" if is_linked1 else "[bold red]✘[/bold red]"
        row.extend([k1, p1.upper(), status1])

        # Col 2
        if i + 1 < len(keys):
            k2 = keys[i+1]
            p2 = p_mapping[k2]
            is_linked2 = False
            if p2 in ["ollama", "vllm", "sglang", "laguna", "llama_cpp", "gpt4all", "local"]:
                is_linked2 = config.get(f"{p2}_host") is not None
            else:
                is_linked2 = get_api_key(p2) is not None
            status2 = "[bold green]✓[/bold green]" if is_linked2 else "[bold red]✘[/bold red]"
            row.extend([k2, p2.upper(), status2])
        else:
            row.extend(["", "", ""])
        
        status_table.add_row(*row)

    console.print(status_table)
    
    choice = Prompt.ask("Select mode or provider", choices=["a", "s", "x", "m", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "g", "k", "p", "r", "l", "v", "y", "f", "e", "o", "c", "i", "s", "u", "z", "b"], default="b")
    
    if choice == "a":
        config["model_mode"] = "auto-offline"
        save_config(config)
        console.print("[green]✅ Switched to Auto-Offline mode. JARVIS will now stay local.[/green]")
        return
    elif choice == "s":
        config["model_mode"] = "auto-online"
        save_config(config)
        console.print("[green]✅ Switched to Auto-Online mode. Prioritizing cloud intelligence.[/green]")
        return
    elif choice == "x":
        config["model_mode"] = "auto-mixed"
        save_config(config)
        console.print("[green]✅ Switched to Auto-Mixed mode. JARVIS will now manage connectivity.[/green]")
        return
    elif choice == "m":
        config["model_mode"] = "manual"
        save_config(config)
        console.print("[green]✅ Switched to Manual mode. Please select your provider below.[/green]")
        return

    p_mapping = {
        "1": "ollama", "2": "openai", "3": "gemini", "4": "claude", "5": "cohere", 
        "6": "mistral", "7": "nvidia", "8": "glm", "9": "deepseek", "0": "qwen",
        "g": "gemma", "k": "kimi", "p": "perplexity", "r": "granite", "l": "laguna",
        "v": "vllm", "y": "sglang", "f": "lfm", "e": "essential", "o": "olmo",
        "c": "cogito", "i": "minimax", "s": "stability", "u": "upstage", "z": "groq",
        "x": "xiaomi", "t": "tencent", "q": "kwaipilot"
    }
    if choice in p_mapping:
        config["model_mode"] = "manual"
        provider = p_mapping[choice]
        config["provider"] = provider
        models = {
            "ollama": ["nave433/jarvis", "llama3.3", "llama3.2", "phi4", "muse-spark"],
            "openai": ["gpt-5.5", "gpt-4o", "o1-preview"],
            "gemini": ["gemini-3.1-pro", "gemini-3-flash-preview"],
            "claude": ["claude-4.7", "claude-3-5-sonnet-20240620"],
            "cohere": ["command-r-plus", "command-r"],
            "mistral": ["mistral-medium-3.5", "mistral-large-latest"],
            "nvidia": ["nemotron-3-super", "nemotron-3-nano"],
            "glm": ["glm-5.1", "glm-5", "glm-4.7"],
            "deepseek": ["deepseek-v4-pro", "deepseek-v3.2"],
            "qwen": ["qwen3.6", "qwen3.5"],
            "gemma": ["gemma-4-27b", "gemma-4-9b"],
            "kimi": ["kimi-k2.6", "kimi-k2.5"],
            "perplexity": ["llama-3.1-sonar-huge-128k-online"],
            "granite": ["granite-4.1", "granite-3.1-8b-instruct"],
            "laguna": ["laguna-xs.2-33b"],
            "vllm": ["meta-llama/Meta-Llama-3-70B-Instruct"],
            "sglang": ["meta-llama/Meta-Llama-3-8B-Instruct"],
            "lfm": ["lfm2.5-thinking", "lfm2-24b-a2b"],
            "essential": ["rnj-1"],
            "olmo": ["olmo-3.1", "olmo-2"],
            "cogito": ["cogito-2.1"],
            "minimax": ["minimax-m2.7", "minimax-m2.5"],
            "stability": ["stablelm2", "stable-code"],
            "upstage": ["solar-pro"],
            "groq": ["llama-3.3-70b-versatile"],
            "xiaomi": ["mimo-v2.5", "mimo-v2-pro"],
            "tencent": ["hy3-preview"],
            "kwaipilot": ["kat-coder-pro-v2"]
        }
        console.print(f"\n[bold white]Recommended Models for {provider.upper()}:[/bold white]")
        for m in models.get(provider, ["default"]): console.print(f"→ {m}")
        new_model = Prompt.ask("Enter exact model identifier", default=models.get(provider, ["default"])[0])
        config["jarvis_model"] = new_model
        if provider == "gemini": config["gemini_model"] = new_model
        save_config(config)
        console.print(f"[green]✅ Manual Setup Complete: Brain switched to {provider.upper()} ({new_model})[/green]")

def prompts_menu():
    """Custom prompt library management and system instruction control."""
    from core.prompts import load_prompts, save_prompt, delete_prompt, list_prompts
    while True:
        console.print(list_prompts())
        config = load_config()
        current = config.get("active_prompt", "default")
        console.print(Panel(f"Active Role: [bold cyan]{current.upper()}[/bold cyan]", border_style="magenta"))
        
        opts = """
        [1] Set Active - Apply a stored role as the primary instruction set.
        [2] Import Role - Create a new persona or custom system instruction.
        [3] Delete Role - Permanently remove a custom role from your library.
        [b] Back       - Exit prompt management.
        """
        console.print(opts)
        choice = Prompt.ask("Action", choices=["1", "2", "3", "b"], default="b")
        if choice == "1":
            name = Prompt.ask("Enter role name to activate")
            prompts = load_prompts()
            if name in prompts:
                config["active_prompt"] = name
                save_config(config)
                console.print(f"[green]✅ Active system instructions set to '{name}'.[/green]")
            else: console.print(f"[red]❌ Error: Role '{name}' not found in library.[/red]")
        elif choice == "2":
            name = Prompt.ask("New Role Name"); text = Prompt.ask("System Instruction Text")
            console.print(f"[green]✅ {save_prompt(name, text)}[/green]")
        elif choice == "3":
            name = Prompt.ask("Role Name to Delete"); res = delete_prompt(name)
            if "Error" in res: console.print(f"[red]❌ {res}[/red]")
            else: console.print(f"[green]✅ {res}[/green]")
        else: break

def ssh_command(args):
    """Secure shell remote command execution engine."""
    from tools.ssh import run_remote
    if not args:
        host = Prompt.ask("Remote Host (e.g. 192.168.1.50)"); user = Prompt.ask("Username"); cmd = Prompt.ask("Command to execute")
    else:
        parts = args.split(" ", 2)
        if len(parts) < 3:
            console.print("[red]⚠️ Usage: /ssh <host> <user> <command>[/red]")
            return
        host, user, cmd = parts
    
    console.print(f"[bold cyan]🔗 Establishing secure channel to {host} as {user}...[/bold cyan]")
    res = run_remote(host, user, cmd)
    console.print(Panel(str(res), title=f"Remote Execution Result: {host}", border_style="cyan"))

def connect_menu():
    """Streamlined interface to link AI accounts and save API keys."""
    from core.services import set_api_key
    console.print(Panel("🌐 [bold cyan]Account Connection Center[/bold cyan]", border_style="cyan"))
    console.print("Select a provider to get your key and save it to JARVIS:")
    console.print("\n[1] Gemini     | [2] OpenAI      | [3] Anthropic   | [4] Groq (Fast Free)")
    console.print("[5] Together   | [6] Mistral     | [7] DeepSeek    | [8] Perplexity")
    console.print("[9] NVIDIA     | [0] Qwen        | [k] Kimi        | [g] Grok (xAI)")
    console.print("[r] Granite    | [s] Stability   | [u] Upstage     | [c] Cohere")
    console.print("[v] vLLM       | [y] SGLang      | [f] Liquid      | [e] Essential")
    console.print("[l] Laguna XS  | [p] Replit      | [b] Back")
    
    choice = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "k", "g", "r", "s", "u", "c", "v", "y", "f", "e", "l", "p", "b"], default="b")
    
    mapping = {
        "1": {"name": "gemini", "display": "Google Gemini", "url": "https://aistudio.google.com/app/apikey"},
        "2": {"name": "openai", "display": "OpenAI", "url": "https://platform.openai.com/api-keys"},
        "3": {"name": "anthropic", "display": "Anthropic", "url": "https://console.anthropic.com/settings/keys"},
        "4": {"name": "groq", "display": "Groq", "url": "https://console.groq.com/keys"},
        "5": {"name": "together", "display": "Together.ai", "url": "https://api.together.xyz/settings/api-keys"},
        "6": {"name": "mistral", "display": "Mistral AI", "url": "https://console.mistral.ai/api-keys/"},
        "7": {"name": "deepseek", "display": "DeepSeek", "url": "https://platform.deepseek.com/api_keys"},
        "8": {"name": "perplexity", "display": "Perplexity", "url": "https://www.perplexity.ai/settings/api"},
        "9": {"name": "nvidia", "display": "NVIDIA NIM", "url": "https://build.nvidia.com/"},
        "0": {"name": "qwen", "display": "Alibaba Qwen", "url": "https://dashscope.console.aliyun.com/apiKey"},
        "k": {"name": "kimi", "display": "Moonshot Kimi", "url": "https://platform.moonshot.cn/console/api-keys"},
        "g": {"name": "grok", "display": "xAI Grok", "url": "https://console.x.ai/"},
        "r": {"name": "granite", "display": "IBM Granite", "url": "https://cloud.ibm.com/watsonx"},
        "s": {"name": "stability", "display": "Stability AI", "url": "https://key.stability.ai/"},
        "u": {"name": "upstage", "display": "Upstage Solar", "url": "https://console.upstage.ai/"},
        "c": {"name": "cohere", "display": "Cohere", "url": "https://dashboard.cohere.com/api-keys"},
        "v": {"name": "vllm", "display": "vLLM", "host_only": True},
        "y": {"name": "sglang", "display": "SGLang", "host_only": True},
        "f": {"name": "lfm", "display": "Liquid AI", "host_only": True},
        "e": {"name": "essential", "display": "Essential AI", "url": "https://essential.ai/"},
        "l": {"name": "laguna", "display": "Laguna XS.2", "host_only": True},
        "p": {"name": "replit", "display": "Replit API", "url": "https://replit.com/teams/join"}
    }
    
    if choice in mapping:
        info = mapping[choice]
        
        if info.get("host_only"):
            host = Prompt.ask(f"Enter host URL for {info['display']} (e.g. http://localhost:8000)")
            if host:
                config = load_config()
                config[f"{info['name']}_host"] = host
                save_config(config)
                console.print(f"[green]✅ {info['display']} host saved successfully![/green]")
            return

        from core.utils import open_url
        console.print(f"\n[bold]1. Opening login page for {info['display']}:[/bold] {info['url']}")
        open_url(info['url'])
            
        if Confirm.ask(f"Do you want to save your {info['display']} key now?"):
            key_val = Prompt.ask(f"Paste your {info['display']} key", password=True)
            if key_val:
                res = set_api_key(info['name'], key_val)
                if res.get("ok"):
                    console.print(f"[green]✅ {info['display']} key saved securely to keychain![/green]")
                else:
                    console.print(f"[red]❌ Failed to save {info['display']} key.[/red]")
            else:
                console.print("[yellow]Aborted: No key entered.[/yellow]")

def robust_help():
    """Universal Command Reference & Technical Documentation."""
    from rich.markdown import Markdown
    from core.ui import get_main_menu_table
    help_md = """
    # JARVIS Engineering Suite: Core Command Reference
    
    ### 💬 [bold white]/chat [query][/bold white]
    Direct interface with your active LLM. Accesses your project instructions, memories, and current context to provide high-level engineering advice.
    
    ### 🔧 [bold white]/fix [issue/path][/bold white]
    The autonomous agent engine. JARVIS initiates a Research-Strategy-Execution cycle to automatically debug and repair your code. 
    *Tip: Type 'fix project_name' to have JARVIS find it on your system.*
    
    ### 🧪 [bold white]/analyze-file [path][/bold white]
    Specialized security and performance audit. JARVIS performs a deep, microscopic scan of a specific file to identify vulnerabilities, hotspots, and style inconsistencies.

    ### 🩺 [bold white]/doctor[/bold white]
    Complete system self-diagnosis. JARVIS checks its own dependencies, health status of engineering repos, and availability of updates in one unified sweep.

    ### 🧠 [bold white]/memory[/bold white]
    Manage your FAISS vector database. JARVIS uses this to maintain long-term semantic context of all your past projects.

    ### 🎭 [bold white]/personality[/bold white]
    Modify the behavioral DNA of your assistant. Choose from Professional, Sarcastic, Concise, Mentor, or the high-precision Nave-AI.

    ### 📝 [bold white]/prompts[/bold white]
    Access your Persona Library. Apply specialized roles like '@bug_hunter' or '@architect' to any chat or fix request for tailored reasoning.
    
    ### ☁️ [bold white]/cloud[/bold white]
    Cross-platform data bridge. Native integration with Google Drive, Dropbox, and iCloud for remote file management.

    ### 🌐 [bold white]/network[/bold white]
    Networking toolkit. Scan your subnet for other nodes or probe specific targets for open service ports.
    """
    console.print(Panel(Markdown(help_md), title="[bold green]System Documentation & Guide[/bold green]", border_style="green"))
    from rich.align import Align
    console.print(Align.center(get_main_menu_table()))

def cloud_menu():
    """Interactive management for cloud storage platforms."""
    from cli import cloud
    info = """
    [bold white]Unified Cloud Bridge[/bold white]
    
    [1] [bold cyan]Google Drive:[/bold cyan] Browse and fetch files from your G-Drive storage.
    [2] [bold cyan]Dropbox:[/bold cyan] Synchronize and edit files stored in your Dropbox.
    [3] [bold cyan]iCloud Drive:[/bold cyan] Direct access to Apple Cloud files (macOS only).
    """
    console.print(Panel(info, title="Cloud Storage", border_style="cyan"))
    if choice == "1": cloud("gdrive")
    elif choice == "2": cloud("dropbox")
    elif choice == "3": cloud("icloud")
