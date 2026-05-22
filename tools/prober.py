import requests
import socket
import time
from rich.console import Console

console = Console()

COMMON_PORTS = [11434, 1234, 8080, 4891, 8000, 5000, 80]
COMMON_HOSTS = ["localhost", "127.0.0.1", "192.168.1.1", "192.168.1.100", "0.0.0.0"]
ENDPOINTS = ["/api/tags", "/v1/models", "/api/generate"]

def probe_llm_endpoints(timeout_limit=180):
    """
    Search for probable local/network LLM API servers.
    Brute-force style probing of logical addresses and ports.
    """
    start_time = time.time()
    console.print(f"[bold cyan]🔍 Launching Autonomous API Prober (Timeout: {timeout_limit}s)...[/bold cyan]")
    
    found_urls = []
    
    # Simple brute force of common host/port combinations
    for host in COMMON_HOSTS:
        if time.time() - start_time > timeout_limit: break
        
        for port in COMMON_PORTS:
            if time.time() - start_time > timeout_limit: break
            
            url = f"http://{host}:{port}"
            # console.print(f"[dim]Probing {url}...[/dim]")
            
            try:
                # Quick TCP check first
                with socket.create_connection((host, port), timeout=0.1):
                    # If port is open, check endpoints
                    for ep in ENDPOINTS:
                        try:
                            r = requests.get(url + ep, timeout=0.5)
                            if r.status_code == 200:
                                console.print(f"[green]✅ Found active LLM endpoint: {url}{ep}[/green]")
                                found_urls.append(url)
                                break # Move to next port
                        except: continue
            except:
                continue
    
    return found_urls

def find_most_logical_server():
    """Returns the first high-probability server found."""
    results = probe_llm_endpoints(timeout_limit=30) # Shorter search for auto-init
    return results[0] if results else None
