import requests
import json
from core.config import load_config
from tools.hardware import get_node_id

# Placeholder Discovery Server URL
DISCOVERY_SERVER_URL = "https://jarvis-discovery-server.example.com"

def register_node():
    cfg = load_config()
    if not cfg.get("global_p2p_enabled"):
        return None
    
    node_id = get_node_id()
    payload = {
        "node_id": node_id,
        "endpoint": cfg.get("p2p_public_endpoint"),
        "name": cfg.get("jarvis_name", "JARVIS-NODE")
    }
    
    try:
        response = requests.post(f"{DISCOVERY_SERVER_URL}/register", json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        return False

def get_global_peers():
    try:
        response = requests.get(f"{DISCOVERY_SERVER_URL}/peers", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        return []
