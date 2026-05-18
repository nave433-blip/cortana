"""
Service manager: API keys, provider validation, model listing, routing, adapters.

Adds support for 'nemotron' and 'qwen', robust Ollama repair helper, and normalized error types.
"""

from typing import Dict, Optional, List, Any
import requests
import json
import os
import time
import webbrowser
import keyring
import shutil
import subprocess
from core.config import load_config, save_config
from rich.console import Console

console = Console()

API_KEYS_KEY = "api_keys"
KEYRING_SERVICE_NAME = "jarvis_cli"
DEFAULT_MODELS_KEY = "default_models"
KNOWN_PROVIDERS = [
    "openai", "ollama", "anthropic", "gemini", "mistral", "gpt4all", "llama_cpp", "vllm", "sglang", 
    "nemotron", "qwen", "deepseek", "kimi", "perplexity", "granite", "laguna", "gemma", "together", 
    "glm", "minimax", "lfm", "essential", "olmo", "cogito", "meta", "microsoft", "minicpm", 
    "smollm", "tii", "nous", "lg", "cohere", "yi", "upstage", "groq", "internlm", 
    "athene", "stability", "reflection", "z_ai", "midjourney", "flux", "sora", "kling", "whisper",
    "wolfram", "polly", "heygen", "veo", "mindsdb", "xiaomi", "tencent", "kwaipilot", "replit", "local"
]

# Key/model utilities
def _load_keys() -> Dict[str, str]:
    cfg = load_config()
    return cfg.get(API_KEYS_KEY, {})

def _save_keys(keys: Dict[str, str]):
    cfg = load_config()
    cfg[API_KEYS_KEY] = keys
    save_config(cfg)

def set_api_key(provider: str, key: str):
    try:
        keyring.set_password(KEYRING_SERVICE_NAME, provider.lower(), key)
    except Exception as e:
        console.print(f"[red]Failed to save key in keyring: {e}[/red]")
        # Fallback to config if keyring fails
        keys = _load_keys()
        keys[provider.lower()] = key
        _save_keys(keys)
    return {"ok": True, "provider": provider.lower()}

def get_api_key(provider: str) -> Optional[str]:
    # First try keyring
    try:
        key = keyring.get_password(KEYRING_SERVICE_NAME, provider.lower())
        if key: return key
    except Exception:
        pass

    # Fallback to config file
    key = _load_keys().get(provider.lower())
    if key:
        return key

    # Fallback to environment variables
    env_keys = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "nemotron": "NEMOTRON_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "vllm": "VLLM_API_KEY",
        "sglang": "SGLANG_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "kimi": "MOONSHOT_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "granite": "WATSONX_API_KEY",
        "laguna": "LAGUNA_API_KEY",
        "gemma": "GEMMA_API_KEY",
        "glm": "GLM_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "lfm": "LIQUID_API_KEY",
        "essential": "ESSENTIAL_API_KEY",
        "olmo": "OLMO_API_KEY",
        "cogito": "COGITO_API_KEY",
        "meta": "META_API_KEY",
        "microsoft": "AZURE_API_KEY",
        "cohere": "COHERE_API_KEY",
        "yi": "YI_API_KEY",
        "upstage": "UPSTAGE_API_KEY",
        "groq": "GROQ_API_KEY",
        "together": "TOGETHER_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "internlm": "INTERNLM_API_KEY",
        "stability": "STABILITY_API_KEY",
        "midjourney": "MIDJOURNEY_API_KEY",
        "flux": "FLUX_API_KEY",
        "sora": "OPENAI_API_KEY",
        "kling": "KLING_API_KEY",
        "whisper": "OPENAI_API_KEY",
        "wolfram": "WOLFRAM_APP_ID",
        "polly": "AWS_SECRET_KEY",
        "heygen": "HEYGEN_API_KEY",
        "veo": "GEMINI_API_KEY",
        "mindsdb": "MINDSDB_API_KEY",
        "xiaomi": "XIAOMI_API_KEY",
        "tencent": "TENCENT_API_KEY",
        "kwaipilot": "KWAIPILOT_API_KEY",
        "replit": "REPLIT_API_KEY"
    }
    env_var = env_keys.get(provider.lower())
    if env_var:
        return os.getenv(env_var)
    return None

def set_key_for_litellm(provider: str):
    """Fetch key from secure storage and set in os.environ for litellm."""
    key = get_api_key(provider)
    if key:
        env_map = {
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
            "together": "TOGETHER_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY"
        }
        os.environ[env_map.get(provider.lower(), f"{provider.upper()}_API_KEY")] = key
    return key

def unset_api_key(provider: str):
    try:
        keyring.delete_password(KEYRING_SERVICE_NAME, provider.lower())
    except Exception:
        pass

    keys = _load_keys()
    if provider.lower() in keys:
        del keys[provider.lower()]
        _save_keys(keys)
    return {"ok": True, "provider": provider.lower()}

def _load_default_models() -> Dict[str, str]:
    cfg = load_config()
    return cfg.get(DEFAULT_MODELS_KEY, {})

def _save_default_models(d: Dict[str, str]):
    cfg = load_config()
    cfg[DEFAULT_MODELS_KEY] = d
    save_config(cfg)

def set_default_model(provider: str, model_name: str):
    d = _load_default_models()
    d[provider.lower()] = model_name
    _save_default_models(d)
    return {"ok": True, "provider": provider.lower(), "model": model_name}

def get_default_model(provider: str) -> Optional[str]:
    return _load_default_models().get(provider.lower())

def get_connected_providers() -> List[str]:
    """Return a list of all providers that have an API key or host configured."""
    connected = []
    cfg = load_config()
    for p in KNOWN_PROVIDERS:
        if p == "ollama":
            if cfg.get("ollama_host") or cfg.get("ollama_hosts"): connected.append(p)
            continue
        
        # Check for host-based providers
        if f"{p}_host" in cfg and cfg.get(f"{p}_host"):
            connected.append(p)
            continue
            
        # Check for key-based providers
        if get_api_key(p):
            connected.append(p)
            
    return connected

# --------------------
# Validation helpers (enhanced)
# --------------------
def validate_gemini(key: str, timeout: float = 5.0) -> Dict:
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return {"ok": True, "provider": "gemini", "note": "Gemini key validated"}
        if r.status_code == 400:
            return {"ok": False, "error": "Gemini key invalid", "error_type": "unauthorized"}
        return {"ok": False, "error": f"Gemini error {r.status_code}", "error_type": "other"}
    except Exception as e:
        return {"ok": False, "error": str(e), "error_type": "unreachable"}

def validate_openai(key: str, timeout: float = 5.0) -> Dict:
    url = "https://api.openai.com/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return {"ok": True, "provider": "openai", "models_count": len(r.json().get("data", []))}
        if r.status_code == 401:
            return {"ok": False, "error": "Unauthorized: invalid OpenAI key", "error_type": "unauthorized"}
        return {"ok": False, "error": f"OpenAI returned HTTP {r.status_code}", "error_type": "other"}
    except Exception as e:
        return {"ok": False, "error": str(e), "error_type": "unreachable"}

def validate_ollama(host: str, timeout: float = 2.0) -> Dict:
    """
    Probes common Ollama endpoints and returns a helpful status.
    """
    host = host.rstrip("/")
    endpoints = ["/api/tags", "/api/models", "/api/health", "/api/completions", ""]
    last_exc = None
    for p in endpoints:
        url = host + p if p else host
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return {"ok": True, "provider": "ollama", "endpoint": url}
            if r.status_code == 401:
                return {"ok": False, "error": "Ollama requires authentication (401)", "error_type": "auth", "endpoint": url}
            if r.status_code == 404:
                continue
            if 400 <= r.status_code < 500:
                return {"ok": False, "error": f"Ollama returned HTTP {r.status_code}", "error_type": "auth", "endpoint": url}
        except requests.exceptions.RequestException as e:
            last_exc = e
            continue
    return {"ok": False, "error": f"Could not reach Ollama at {host}. Error: {last_exc}", "error_type": "unreachable"}

def validate_generic_host(host: str, timeout: float = 2.0) -> Dict:
    try:
        r = requests.get(host, timeout=timeout)
        return {"ok": True, "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e), "error_type": "unreachable"}

def validate_provider_connection(provider: str, extra: Optional[Dict[str, Any]] = None) -> Dict:
    provider = provider.lower()
    extra = extra or {}
    if provider == "openai":
        key = extra.get("key") or get_api_key("openai")
        if not key: return {"ok": False, "error": "OpenAI key not configured", "error_type": "unauthorized"}
        return validate_openai(key)
    if provider == "ollama":
        cfg = load_config()
        host = extra.get("host") or cfg.get("ollama_host")
        if not host: return {"ok": False, "error": "Ollama host not configured", "error_type": "unreachable"}
        return validate_ollama(host)
    if provider == "gemini":
        key = extra.get("key") or get_api_key("gemini")
        if not key: return {"ok": False, "error": "Gemini key not configured", "error_type": "unauthorized"}
        return validate_gemini(key)
    if provider in ("gpt4all", "llama_cpp", "vllm", "sglang", "nemotron", "qwen", "local"):
        cfg = load_config()
        host = extra.get("host") or cfg.get(f"{provider}_host")
        if not host: return {"ok": False, "error": f"No host configured for {provider}", "error_type": "unreachable"}
        return validate_generic_host(host)
    if provider == "anthropic":
        key = extra.get("key") or get_api_key("anthropic")
        if not key: return {"ok": False, "error": "Anthropic key not configured", "error_type": "unauthorized"}
        return {"ok": True, "provider": "anthropic", "note": "Key present (no network check)"}
    return {"ok": False, "error": f"Provider '{provider}' not supported for validation.", "error_type": "other"}

# --------------------
# Model listing
# --------------------
def list_models_for_provider(provider: str, extra: Optional[Dict[str, Any]] = None) -> Dict:
    provider = provider.lower()
    extra = extra or {}
    if provider == "openai":
        key = extra.get("key") or get_api_key("openai")
        if not key: return {"ok": False, "error": "OpenAI key required", "error_type": "unauthorized"}
        try:
            r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=5)
            if r.status_code == 200:
                models = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
                return {"ok": True, "models": models}
            return {"ok": False, "error": f"OpenAI error {r.status_code}", "error_type": "other"}
        except Exception as e:
            return {"ok": False, "error": str(e), "error_type": "unreachable"}
    if provider == "ollama":
        cfg = load_config()
        host = extra.get("host") or cfg.get("ollama_host")
        if not host: return {"ok": False, "error": "Ollama host not configured", "error_type": "unreachable"}
        for p in ("/api/tags", "/api/models"):
            try:
                r = requests.get(host.rstrip("/") + p, timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    return {"ok": True, "models": models}
            except: continue
        return {"ok": False, "error": "Could not fetch models from Ollama", "error_type": "unreachable"}
    
    fallback = {
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
        "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
        "gemini": ["gemini-1.5-pro", "gemini-2.0-flash"],
    }
    return {"ok": True, "models": fallback.get(provider, [])}

# --------------------
# Call entrypoints
# --------------------
def call_model(provider: str, messages_or_text: Any, model: Optional[str] = None, temperature: float = 0.2, timeout: float = 30.0) -> Dict:
    import litellm
    provider = provider.lower()
    set_key_for_litellm(provider)
    
    if isinstance(messages_or_text, str):
        messages = [{"role": "user", "content": messages_or_text}]
    else:
        messages = messages_or_text

    try:
        # Construct model string if provider prefix missing
        model_str = model
        if model and '/' not in model and provider not in ["openai", "anthropic", "gemini"]:
             model_str = f"{provider}/{model}"
        elif not model:
            # Fallback to sensible defaults
            defaults = {
                "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-sonnet-20241022",
                "gemini": "gemini-1.5-flash",
                "groq": "groq/llama-3.3-70b-versatile",
                "together": "together_ai/Qwen/Qwen2.5-72B-Instruct",
                "deepseek": "deepseek/deepseek-chat"
            }
            model_str = defaults.get(provider, f"ollama/llama3")

        response = litellm.completion(
            model=model_str,
            messages=messages,
            temperature=temperature,
            timeout=timeout
        )
        return {"ok": True, "text": response.choices[0].message.content, "provider": provider, "model": model_str}
    except Exception as e:
        return {"ok": False, "error": str(e), "error_type": "call_failed"}

# --------------------
# Ollama helper logic
# --------------------
def ensure_ollama() -> Dict:
    cfg = load_config()
    host = cfg.get("ollama_host", "http://localhost:11434")
    v = validate_ollama(host, timeout=1.0)
    if v.get("ok"):
        return {"ok": True, "message": f"Ollama is running at {host}", "host": host}
    
    # Attempt repair
    console.print(f"[yellow]Ollama not reachable at {host}. Attempting auto-repair...[/yellow]")
    rep = repair_ollama(host)
    if rep.get("fixed"):
        return {"ok": True, "message": "Ollama repaired.", "host": cfg.get("ollama_host")}
    
    return {"ok": False, "error": "Ollama is not responding. Please ensure it is installed and running.", "error_type": "missing"}

def repair_ollama(host: Optional[str] = None) -> Dict:
    cfg = load_config()
    candidates = [host] if host else []
    candidates += [cfg.get("ollama_host"), "http://localhost:11434", "http://127.0.0.1:11434"]
    candidates = list(filter(None, list(set(candidates))))

    for h in candidates:
        try:
            r = requests.get(h.rstrip("/") + "/api/tags", timeout=2)
            if r.status_code == 200:
                cfg["ollama_host"] = h
                save_config(cfg)
                return {"fixed": True, "host": h}
        except: continue

    # MacOS specific
    if sys.platform == "darwin":
        os.system("open -a Ollama")
        time.sleep(5)
        for h in candidates:
            try:
                if requests.get(h.rstrip("/") + "/api/tags", timeout=2).status_code == 200:
                    cfg["ollama_host"] = h
                    save_config(cfg)
                    return {"fixed": True, "host": h}
            except: continue
            
    return {"fixed": False}
