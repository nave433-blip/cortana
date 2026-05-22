import os
import webbrowser
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from core.config import load_config, save_config, get_env_with_config
from core.services import get_api_key, set_api_key, validate_provider_connection, repair_ollama
from core.utils import open_url

console = Console()

class AuthManager:
    """Manages the startup login sequence and account linking for JARVIS."""

    PROVIDERS = {
        "openai": {"display": "OpenAI", "url": "https://platform.openai.com/api-keys"},
        "gemini": {"display": "Google Gemini", "url": "https://aistudio.google.com/app/apikey"},
        "anthropic": {"display": "Anthropic", "url": "https://console.anthropic.com/settings/keys"},
        "gemma": {"display": "Gemma 4", "url": "https://aistudio.google.com/app/apikey"},
        "cohere": {"display": "Cohere", "url": "https://dashboard.cohere.com/api-keys"},
        "mistral": {"display": "Mistral AI", "url": "https://console.mistral.ai/api-keys/"},
        "nvidia": {"display": "NVIDIA NIM", "url": "https://build.nvidia.com/"},
        "glm": {"display": "Z.ai GLM", "url": "https://open.bigmodel.cn/usercenter/apikeys"},
        "github": {"display": "GitHub", "url": "https://github.com/settings/tokens"},
        "deepseek": {"display": "DeepSeek", "url": "https://platform.deepseek.com/api_keys"},
        "qwen": {"display": "Alibaba Qwen", "url": "https://dashscope.console.aliyun.com/apiKey"},
        "kimi": {"display": "Moonshot Kimi", "url": "https://platform.moonshot.cn/console/api-keys"},
        "perplexity": {"display": "Perplexity", "url": "https://www.perplexity.ai/settings/api"},
        "granite": {"display": "IBM Granite", "url": "https://cloud.ibm.com/watsonx"},
        "stability": {"display": "Stability AI", "url": "https://key.stability.ai/"},
        "upstage": {"display": "Upstage Solar", "url": "https://console.upstage.ai/"},
        "groq": {"display": "Groq", "url": "https://console.groq.com/keys"},
        "gumloop": {"display": "Gumloop", "url": "https://www.gumloop.com/account"},
        "wolfram": {"display": "Wolfram Alpha", "url": "https://developer.wolframalpha.com/"},
        "polly": {"display": "Amazon Polly", "url": "https://console.aws.amazon.com/polly/"},
        "heygen": {"display": "HeyGen", "url": "https://app.heygen.com/settings?nav=API"},
        "veo": {"display": "Google VEO", "url": "https://aistudio.google.com/"},
        "mindsdb": {"display": "MindsDB", "url": "https://cloud.mindsdb.com/"},
        "midjourney": {"display": "Midjourney", "url": "https://www.midjourney.com/account/"},
        "flux": {"display": "FLUX AI", "url": "https://replicate.com/black-forest-labs"},
        "sora": {"display": "OpenAI Sora", "url": "https://platform.openai.com/"},
        "kling": {"display": "Kling AI", "url": "https://klingai.com/"},
        "whisper": {"display": "OpenAI Whisper", "url": "https://platform.openai.com/"},
        "vllm": {"display": "vLLM", "host_only": True},
        "sglang": {"display": "SGLang", "host_only": True},
        "lfm": {"display": "Liquid AI", "host_only": True},
        "essential": {"display": "Essential AI", "url": "https://essential.ai/"},
        "xiaomi": {"display": "Xiaomi MiMo", "url": "https://ai.mi.com/"},
        "tencent": {"display": "Tencent Hy3", "url": "https://cloud.tencent.com/product/hunyuan"},
        "kwaipilot": {"display": "Kwaipilot", "url": "https://kwaipilot.com/"},
        "replit": {"display": "Replit", "url": "https://replit.com/teams/join"},
        "laguna": {"display": "Laguna XS.2", "host_only": True}
    }

    @staticmethod
    def run_startup_login():
        """Executed on launch to ensure critical services are connected."""
        config = load_config()
        
        # 1. Check Primary Provider
        primary = config.get("provider", "ollama")
        console.print(f"[dim]Verifying primary intelligence: {primary.upper()}...[/dim]")
        
        status = validate_provider_connection(primary)
        if not status.get("ok"):
            console.print(Panel(f"[bold yellow]⚠️ Primary Provider ({primary.upper()}) Disconnected[/bold yellow]\n{status.get('error')}", border_style="yellow"))
            
            if primary == "ollama":
                if Confirm.ask("Attempt to repair/reconnect Ollama?"):
                    repair_ollama()
            else:
                if Confirm.ask(f"Link or configure your {primary.upper()} backend now?"):
                    AuthManager.link_account(primary)

        # 2. Check for missing critical cloud fallbacks
        missing_fallbacks = []
        for p in ["openai", "gemini"]:
            if not get_api_key(p):
                missing_fallbacks.append(p)

        if missing_fallbacks:
            console.print(f"\n[dim]Note: Missing cloud fallback keys for: {', '.join(missing_fallbacks)}[/dim]")
            if Confirm.ask("Would you like to link a fallback cloud account for higher reliability?"):
                for p in missing_fallbacks:
                    if Confirm.ask(f"Link {p.upper()}?"):
                        AuthManager.link_account(p)

    @staticmethod
    def link_account(provider_name):
        """Interactive flow to link a specific service account."""
        info = AuthManager.PROVIDERS.get(provider_name.lower())
        display_name = info["display"] if info else provider_name.upper()
        url = info["url"] if info and not info.get("host_only") else None

        console.print(Panel(f"🔗 [bold cyan]Linking {display_name} Account[/bold cyan]", border_style="cyan"))
        
        if info and info.get("host_only"):
            host = Prompt.ask(f"Enter host URL for {display_name} (e.g. http://localhost:8000)")
            if host:
                config = load_config()
                config[f"{provider_name.lower()}_host"] = host
                save_config(config)
                console.print(f"[green]✅ {display_name} host saved successfully![/green]")
            return

        if url:
            console.print(f"Opening developer dashboard: [link={url}]{url}[/link]")
            open_url(url)
        
        key = Prompt.ask(f"Enter API Key / Token for {display_name}", password=True)
        if key:
            res = set_api_key(provider_name, key)
            if res.get("ok"):
                console.print(f"[green]✅ {display_name} linked successfully![/green]")
                # Verify connection immediately
                v = validate_provider_connection(provider_name)
                if v.get("ok"):
                    console.print(f"[dim]Connection verified.[/dim]")
                else:
                    console.print(f"[yellow]⚠️ Key saved, but verification failed: {v.get('error')}[/yellow]")
            else:
                console.print(f"[red]❌ Failed to save key for {display_name}.[/red]")
        else:
            console.print("[yellow]Skipped.[/yellow]")
