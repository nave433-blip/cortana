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
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "online", "name": "JARVIS-PEER"}).encode())
            return

        if not check_permission(peer_ip, action):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Permission denied")
            return

        if action == "edit_file":
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

def start_server_background():
    t = threading.Thread(target=run_p2p_server, daemon=True)
    t.start()
    return t
