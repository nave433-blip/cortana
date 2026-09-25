import psutil
from rich.console import Console
from rich.panel import Panel
from core.config import load_config, save_config

console = Console()

def get_hardware_specs():
    cpu_count = psutil.cpu_count(logical=False)
    ram_total = psutil.virtual_memory().total / (1024 ** 3) # GB
    
    gpu_name = "None"
    gpu_vram = 0
    try:
        import subprocess
        res = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            parts = res.stdout.strip().split(',')
            gpu_name = parts[0].strip()
            gpu_vram = float(parts[1].strip()) / 1024.0 # GB
    except Exception:
        pass

    return {
        "cpu_cores": cpu_count,
        "ram_gb": ram_total,
        "gpu_name": gpu_name,
        "gpu_vram_gb": gpu_vram
    }

def analyze_and_suggest_tier(specs):
    # Logic for tiering:
    # Low: < 8GB RAM or no GPU
    # Medium: 8-16GB RAM + some GPU
    # High: > 16GB RAM + 8GB+ VRAM
    
    if specs["ram_gb"] < 7.5 or specs["gpu_vram_gb"] < 2:
        return "low", "Low-end machine detected. Standard cloud models (OpenAI, Gemini) recommended for speed."
    elif specs["ram_gb"] < 15.5 or specs["gpu_vram_gb"] < 7.5:
        return "medium", "Mid-range machine detected. Can run small local models (Llama 3 8B, Phi-4) comfortably."
    else:
        return "high", "High-performance machine detected! Full local Hive Mind capabilities and large models (Llama 4 70B+) enabled."

def run_hardware_check_on_startup():
    specs = get_hardware_specs()
    tier, suggestion = analyze_and_suggest_tier(specs)
    
    cfg = load_config()
    cfg["machine_tier"] = tier
    save_config(cfg)
    
    console.print(Panel(
        f"[bold cyan]Hardware Audit:[/bold cyan]\n"
        f"CPU: {specs['cpu_cores']} cores | RAM: {specs['ram_gb']:.1f}GB | GPU: {specs['gpu_name']} ({specs['gpu_vram_gb']:.1f}GB)\n\n"
        f"Result: [bold green]{tier.upper()} TIER[/bold green]\n"
        f"[dim]{suggestion}[/dim]",
        title="Startup Diagnostic",
        border_style="cyan"
    ))
    
    if tier == "low" and cfg.get("provider") == "ollama":
        from rich.prompt import Confirm
        from core.approvals import confirm
        if confirm("Your machine might struggle with local LLMs. Switch to cloud-first mode (Gemini/OpenAI)?"):
            cfg["provider"] = "gemini"
            save_config(cfg)
            console.print("[green]✓ Switched to Gemini as primary provider.[/green]")
