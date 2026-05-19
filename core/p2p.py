import http.server
import socketserver
import json
import os
import threading
from rich.console import Console
from rich.prompt import Confirm, Prompt
from pathlib import Path

console = Console()

PERMISSION_FILE = Path(os.path.expanduser("~/.jarvis/permissions.json"))

def load_permissions():
    if not PERMISSION_FILE.exists():
        return {}
    try:
        with open(PERMISSION_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_permissions(permissions):
    PERMISSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PERMISSION_FILE, "w") as f:
        json.dump(permissions, f, indent=4)

def check_permission(peer_ip, action):
    permissions = load_permissions()
    peer_perms = permissions.get(peer_ip, {})
    choice = peer_perms.get(action)

    if choice == "always":
        return True
    if choice == "never":
        return False

    # Manual prompt if not remembered
    console.print(f"\n[bold yellow]⚠️ REMOTE REQUEST:[/bold yellow] JARVIS instance at [cyan]{peer_ip}[/cyan] wants to [bold magenta]{action}[/bold magenta].")
    options = {
        "1": "always",
        "2": "this once",
        "3": "never",
        "4": "not right now"
    }
    console.print("[1] Always | [2] This once | [3] Never | [4] Not right now")
    ans = Prompt.ask("Choice", choices=["1", "2", "3", "4"], default="4")
    
    final_choice = options[ans]
    
    if final_choice == "always":
        peer_perms[action] = "always"
        permissions[peer_ip] = peer_perms
        save_permissions(permissions)
        return True
    if final_choice == "this once":
        return True
    if final_choice == "never":
        peer_perms[action] = "never"
        permissions[peer_ip] = peer_perms
        save_permissions(permissions)
        return False
    return False

class JarvisP2PHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        peer_ip = self.client_address[0]
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        action = data.get("action")
        
        if action == "status":
            from core.update import CURRENT_VERSION
            from core.config import load_config
            cfg = load_config()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status_data = {
                "status": "online",
                "name": cfg.get("jarvis_name", "JARVIS-PEER"),
                "version": CURRENT_VERSION,
                "model": cfg.get("jarvis_model", "unknown"),
                "local_models": cfg.get("detected_local_models", []),
                "p2p_enabled": cfg.get("p2p_enabled", True)
            }
            self.wfile.write(json.dumps(status_data).encode())
            return

        if action == "list_tokens":
            from core.services import list_available_keys
            tokens = list_available_keys()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(tokens).encode())
            return

        if not check_permission(peer_ip, action):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Permission denied")
            return

        if action == "get_token":
            from core.services import get_api_key
            provider = data.get("provider")
            key = get_api_key(provider)
            if key:
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(key.encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Token not found")

        elif action == "edit_file":
            path = data.get("path")
            content = data.get("content")
            try:
                full_path = Path(os.path.expanduser(path))
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"File updated successfully")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())

        elif action == "read_file":
            path = data.get("path")
            try:
                full_path = Path(os.path.expanduser(path))
                if not full_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                with open(full_path, "r") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(content.encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())

        elif action == "think":
            task = data.get("task")
            model = data.get("model")
            try:
                from core.brain import think_structured
                # Process the remote task using our local hardware/brain
                res = think_structured("P2P Hive Mind Remote Task", task, model=model)
                if res.get("ok"):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"text": res.get("text"), "provider": res.get("provider")}).encode())
                else:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(str(res.get("error")).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())

def run_p2p_server(port=11435):
    with socketserver.TCPServer(("", port), JarvisP2PHandler) as httpd:
        console.print(f"[green]🚀 JARVIS P2P Server listening on port {port}...[/green]")
        httpd.serve_forever()

import socket
import requests
from concurrent.futures import ThreadPoolExecutor

def scan_for_jarvis_peers(port=11435):
    """Scan the local subnet for other JARVIS instances."""
    from tools.network import get_local_ip
    local_ip = get_local_ip()
    prefix = ".".join(local_ip.split(".")[:-1]) + "."
    
    found_peers = []
    
    def check_peer(ip):
        try:
            r = requests.post(f"http://{ip}:{port}", json={"action": "status"}, timeout=0.5)
            if r.status_code == 200:
                return ip
        except:
            pass
        return None

    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(check_peer, [prefix + str(i) for i in range(1, 255)])
        for res in results:
            if res:
                found_peers.append(res)
    
    return found_peers

def send_remote_command(peer_ip, action, params, port=11435):
    """Send a command to a remote JARVIS instance."""
    url = f"http://{peer_ip}:{port}"
    data = {"action": action, **params}
    try:
        r = requests.post(url, json=data, timeout=30)
        if r.status_code == 200:
            return {"ok": True, "data": r.text}
        elif r.status_code == 403:
            return {"ok": False, "error": "Permission denied by remote JARVIS."}
        else:
            return {"ok": False, "error": f"Remote error {r.status_code}: {r.text}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def p2p_status_report():
    """Scan and display a detailed report of all JARVIS peers on the network."""
    from rich.table import Table
    from rich.live import Live
    
    table = Table(title="JARVIS P2P Swarm Status", border_style="cyan")
    table.add_column("Peer IP", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Version", style="dim")
    table.add_column("Active Model", style="magenta")
    table.add_column("Latency", justify="right")
    
    console.print("[bold cyan]📡 Pinging JARVIS instances on local subnet...[/bold cyan]")
    
    with Live(table, refresh_per_second=4):
        from tools.network import get_local_ip
        local_ip = get_local_ip()
        prefix = ".".join(local_ip.split(".")[:-1]) + "."
        port = 11435
        
        def ping_peer(ip):
            start = time.time()
            try:
                r = requests.post(f"http://{ip}:{port}", json={"action": "status"}, timeout=0.8)
                latency = f"{(time.time() - start)*1000:.1f}ms"
                if r.status_code == 200:
                    return ip, r.json(), latency
            except:
                pass
            return None

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(ping_peer, prefix + str(i)) for i in range(1, 255)]
            for future in futures:
                res = future.result()
                if res:
                    ip, data, lat = res
                    models_str = ", ".join(data.get("local_models", []))
                    if not models_str: models_str = "None"
                    
                    table.add_row(
                        ip, 
                        data.get("name", "Unknown"), 
                        data.get("version", "???"), 
                        f"{data.get('model', '???')} (Models: {models_str})", 
                        lat
                    )

    if table.row_count == 0:
        console.print("[yellow]No other JARVIS instances detected.[/yellow]")

def p2p_token_menu():
    """Interactive menu for discovering and requesting tokens from peers."""
    from rich.table import Table
    
    console.print("[bold cyan]Subnet Token Discovery[/bold cyan]")
    peers = scan_for_jarvis_peers()
    
    if not peers:
        console.print("[yellow]No JARVIS peers found on local network.[/yellow]")
        return

    table = Table(title="Available Peer Tokens", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim"); table.add_column("Peer IP", style="cyan"); table.add_column("Available Tokens", style="white")
    
    peer_token_map = {}
    for i, ip in enumerate(peers):
        res = send_remote_command(ip, "list_tokens", {})
        if res["ok"]:
            tokens = json.loads(res["data"])
            token_str = ", ".join(tokens) if tokens else "[dim]None[/dim]"
            table.add_row(str(i+1), ip, token_str)
            peer_token_map[str(i+1)] = {"ip": ip, "tokens": tokens}
        else:
            table.add_row(str(i+1), ip, f"[red]Error: {res['error']}[/red]")
            
    console.print(table)
    
    choice = Prompt.ask("\nEnter ID to request token (or 'b' to go back)", default="b")
    if choice in peer_token_map:
        peer = peer_token_map[choice]
        if not peer["tokens"]:
            console.print("[yellow]This peer has no tokens to share.[/yellow]")
            return
            
        token_choice = Prompt.ask(f"Select token to request from {peer['ip']}", choices=peer["tokens"])
        console.print(f"[bold yellow]Requesting {token_choice} token from {peer['ip']}...[/bold yellow]")
        console.print("[dim]Note: The remote user must manually approve this request.[/dim]")
        
        res = send_remote_command(peer["ip"], "get_token", {"provider": token_choice})
        if res["ok"]:
            key = res["data"]
            from core.services import set_api_key
            set_api_key(token_choice, key)
            console.print(f"[bold green]✅ {token_choice.upper()} token successfully received and saved locally![/bold green]")
        else:
            console.print(f"[red]❌ Failed to get token: {res['error']}[/red]")

def start_server_background():
    t = threading.Thread(target=run_p2p_server, daemon=True)
    t.start()
    return t
