import requests
import json
from core.config import load_config
from tools.hardware import get_node_id
from rich.console import Console

console = Console()

# Discovery server URL. There is no hosted JARVIS discovery service;
# set "discovery_server_url" in the config to point at your own.
DISCOVERY_SERVER_URL = "https://jarvis-discovery-server.example.com"

def _server_url(cfg) -> str | None:
    url = cfg.get("discovery_server_url") or DISCOVERY_SERVER_URL
    if "example.com" in url:
        return None  # placeholder was never replaced with a real server
    if url.startswith("http://"):
        # node_id/endpoint registrations would travel in plaintext
        console.print("[yellow]Global P2P: discovery server URL uses plaintext "
                      "HTTP — node registrations are unencrypted. Prefer https.[/yellow]")
    return url

def register_node():
    cfg = load_config()
    if not cfg.get("global_p2p_enabled"):
        return None

    url = _server_url(cfg)
    if url is None:
        console.print("[yellow]Global P2P: no discovery server configured "
                      "(set 'discovery_server_url' in config). Skipping registration.[/yellow]")
        return False

    node_id = get_node_id()
    payload = {
        "node_id": node_id,
        "endpoint": cfg.get("p2p_public_endpoint"),
        "name": cfg.get("cortana_name", "Cortana")
    }

    try:
        response = requests.post(f"{url}/register", json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        console.print(f"[red]Global P2P registration failed: {e}[/red]")
        return False

def get_global_peers():
    cfg = load_config()
    url = _server_url(cfg)
    if url is None:
        return []
    try:
        response = requests.get(f"{url}/peers", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []
