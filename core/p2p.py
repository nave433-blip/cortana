import http.server
import socketserver
import json
import os
import hmac
import ipaddress
import shutil
import ssl
import subprocess
import threading
import time
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.prompt import Confirm, Prompt
from pathlib import Path
from core.update import CURRENT_VERSION

console = Console()

# SECURITY NOTICE: the P2P protocol is plaintext HTTP with a shared token.
# API keys requested via "get_token" travel unencrypted. Only enable P2P on
# networks you trust, and use a strong p2p_token.
#
# TLS OPT-IN: to encrypt the P2P transport, set "p2p_use_tls": true in
# ~/.jarvis/config.json and point "p2p_tls_certfile"/"p2p_tls_keyfile" at PEM
# files. A self-signed certificate is fine on a trusted LAN; generate one with
#   python3 -c "from core.p2p import generate_self_signed_cert; \
#       generate_self_signed_cert('/path/to/p2p.crt', '/path/to/p2p.key')"
# (equivalently: openssl req -x509 -newkey rsa:2048 -keyout p2p.key -out p2p.crt
#  -days 825 -nodes -subj "/CN=jarvis-p2p").
# TLS clients skip certificate verification by default (verify_tls=False) so
# self-signed certs work; pass verify_tls=True when you have a CA-signed cert
# you want validated. Default behavior (plaintext HTTP) is unchanged.

# Remote file operations are confined to the JARVIS workspace root.
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def _is_path_confined(raw_path: str) -> "Path | None":
    """Resolve a requested path and return it only if it stays inside the workspace."""
    try:
        full = Path(os.path.expanduser(raw_path)).resolve()
    except Exception:
        return None
    try:
        full.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return None
    return full

def _is_private_peer(peer_ip: str) -> bool:
    """Proper private-network classification (the old startswith check missed
    most of 172.16/12 and all IPv6 private ranges)."""
    try:
        ip = ipaddress.ip_address(peer_ip)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False

# P2P Protocol versioning and feature compatibility map
P2P_VERSION = CURRENT_VERSION
P2P_FEATURES = {
    "0.1.7": ["status", "edit_file", "read_file"],
    "0.2.6": ["status", "edit_file", "read_file", "list_tokens", "get_token", "think", "handoff", "execute_chunk"]
}

def is_p2p_compatible(remote_version: str, action: str = "status") -> bool:
    """Check if the remote JARVIS version supports the requested action."""
    supported_features = P2P_FEATURES.get(remote_version, P2P_FEATURES.get("0.1.7"))
    if action == "status": return True
    return action in supported_features

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

    console.print(f"\n[bold yellow]⚠️ REMOTE REQUEST:[/bold yellow] JARVIS instance at [cyan]{peer_ip}[/cyan] wants to [bold magenta]{action}[/bold magenta].")
    options = {"1": "always", "2": "this once", "3": "never", "4": "not right now"}
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

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class JarvisP2PHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        peer_ip = self.client_address[0]
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_response(400); self.end_headers(); return

        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
        except json.JSONDecodeError:
            self.send_response(400); self.end_headers(); return

        action = data.get("action")
        sender_version = data.get("version", "0.1.0")
        auth_token = data.get("token")

        # Security: Check for P2P Token if configured (constant-time compare)
        from core.config import load_config
        cfg = load_config()
        required_token = cfg.get("p2p_token")
        if required_token and not hmac.compare_digest(str(auth_token), str(required_token)):
            if action != "status":
                self.send_response(401); self.end_headers()
                self.wfile.write(b"Unauthorized: Invalid P2P Token"); return

        # Basic WAN restriction: only private/loopback peers may use mutating actions
        is_local = _is_private_peer(peer_ip)
        if not is_local and action not in ["think", "status"]:
             self.send_response(403); self.end_headers()
             self.wfile.write(b"Forbidden: WAN access restricted."); return

        if not is_p2p_compatible(sender_version, action):
            self.send_response(426); self.end_headers()
            self.wfile.write(f"Incompatible Version: Peer is running {sender_version}, but {action} requires a newer build.".encode()); return
        
        if action == "status":
            from core.resource_manager import resource_manager
            health = resource_manager.check_hive_health()
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            status_data = {
                "status": "online",
                "name": cfg.get("jarvis_name", "JARVIS-PEER"),
                "version": CURRENT_VERSION,
                "model": cfg.get("jarvis_model", "unknown"),
                "local_models": cfg.get("detected_local_models", []),
                "p2p_enabled": cfg.get("p2p_enabled", True),
                "hive_load": health
            }
            self.wfile.write(json.dumps(status_data).encode()); return

        if action == "list_tokens":
            from core.services import list_available_keys
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(list_available_keys()).encode()); return

        if not check_permission(peer_ip, action):
            self.send_response(403); self.end_headers()
            self.wfile.write(b"Permission denied"); return

        if action == "get_token":
            from core.services import get_api_key
            key = get_api_key(data.get("provider"))
            if key:
                self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
                self.wfile.write(key.encode())
            else:
                self.send_response(404); self.end_headers(); self.wfile.write(b"Token not found")

        elif action == "read_file":
            file_path = data.get("path")
            full_path = _is_path_confined(file_path) if file_path else None
            if full_path is None:
                self.send_response(403); self.end_headers()
                self.wfile.write(b"Forbidden: path is outside the JARVIS workspace"); return
            try:
                if full_path.is_file():
                    with open(full_path, "r") as f: content = f.read()
                    self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
                    self.wfile.write(content.encode())
                else:
                    self.send_response(404); self.end_headers(); self.wfile.write(b"File not found")
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())

        elif action == "edit_file":
            file_path, old_s, new_s = data.get("path"), data.get("old_string"), data.get("new_string")
            if not all([file_path, old_s, new_s]):
                self.send_response(400); self.end_headers(); return
            full_path = _is_path_confined(file_path)
            if full_path is None:
                self.send_response(403); self.end_headers()
                self.wfile.write(b"Forbidden: path is outside the JARVIS workspace"); return
            from tools.editor import replace_in_file
            try:
                res = replace_in_file(str(full_path), old_s, new_s, interactive=False)
                self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
                self.wfile.write(res.encode())
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())

        elif action == "think":
            from core.resource_manager import resource_manager
            if not resource_manager.check_hive_health()["safe"]:
                self.send_response(503); self.end_headers()
                self.wfile.write(b"Hive Mind Busy: Resource cap reached."); return
            
            task, model, stream = data.get("task"), data.get("model"), data.get("stream", False)
            try:
                if stream:
                    from core.brain import think_stream
                    self.send_response(200); self.send_header('Content-type', 'text/event-stream'); self.end_headers()
                    for chunk in think_stream("P2P Remote Task", task, model=model):
                        self.wfile.write(chunk.encode()); self.wfile.flush()
                else:
                    from core.brain import think_structured
                    res = think_structured("P2P Remote Task", task, model=model)
                    self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                    self.wfile.write(json.dumps(res).encode())
            except Exception as e:
                if not stream: self.send_response(500); self.end_headers()
                self.wfile.write(str(e).encode())

        elif action == "handoff":
            payload = data.get("payload", {})
            keys = payload.get("keys", {})
            fs_edits = payload.get("fs_edits", [])
            console.print(f"\n[bold magenta]🚀 INCOMING HANDOFF FROM {peer_ip}[/bold magenta]")
            if Confirm.ask("Accept this handoff?"):
                from core.services import set_api_key
                for provider, key in keys.items():
                    if Confirm.ask(f"Accept {provider} key?"): set_api_key(provider, key)
                self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
            else:
                self.send_response(403); self.end_headers(); self.wfile.write(b"Rejected")

        elif action == "execute_chunk":
            from core.brain import think_structured
            res = think_structured("P2P Swarm Chunk", data.get("task"))
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(res).encode())

# ---------------------------------------------------------------------------
# Optional TLS (stdlib ssl). All helpers are opt-in; defaults stay plaintext.
# ---------------------------------------------------------------------------

def generate_self_signed_cert(certfile, keyfile=None, hostname="jarvis-p2p"):
    """Generate a self-signed cert/key pair using the openssl CLI.

    Uses an argv list (no shell=True), so paths cannot inject commands.
    Returns (certfile, keyfile) as strings.
    """
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError(
            "openssl CLI not found; install OpenSSL or supply your own PEM files."
        )
    certfile, keyfile = str(certfile), str(keyfile or certfile)
    subprocess.run(
        [openssl, "req", "-x509", "-newkey", "rsa:2048",
         "-keyout", keyfile, "-out", certfile,
         "-days", "825", "-nodes", "-subj", f"/CN={hostname}"],
        check=True, capture_output=True, text=True,
    )
    return certfile, keyfile


def _tls_enabled(use_tls, cfg):
    """Resolve the effective TLS flag: explicit argument wins, else config."""
    if use_tls is None:
        use_tls = bool(cfg.get("p2p_use_tls", False))
    return use_tls


def _p2p_scheme(use_tls, cfg):
    return "https" if _tls_enabled(use_tls, cfg) else "http"


def _build_ssl_context(certfile, keyfile=None):
    """Build a server-side SSLContext from PEM cert/key files."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile or certfile)
    return ctx


def _quiet_insecure_warnings():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def run_p2p_server(port=11435, use_tls=None, certfile=None, keyfile=None):
    """Start the P2P HTTP(S) server.

    TLS is opt-in: pass use_tls=True, or set "p2p_use_tls": true in the config
    together with "p2p_tls_certfile"/"p2p_tls_keyfile". With no flag and no
    config, the server stays plaintext HTTP exactly as before.
    """
    from core.config import load_config
    cfg = load_config()
    use_tls = _tls_enabled(use_tls, cfg)
    threading.Thread(target=run_udp_discovery_listener, args=(port,), daemon=True).start()
    with ThreadedHTTPServer(("", port), JarvisP2PHandler) as httpd:
        scheme = "http"
        if use_tls:
            certfile = certfile or cfg.get("p2p_tls_certfile")
            keyfile = keyfile or cfg.get("p2p_tls_keyfile") or certfile
            if not certfile:
                raise ValueError(
                    "P2P TLS is enabled but no certificate is configured. "
                    "Set 'p2p_tls_certfile' (and 'p2p_tls_keyfile') in "
                    "~/.jarvis/config.json or pass certfile=/keyfile= explicitly."
                )
            httpd.socket = _build_ssl_context(certfile, keyfile).wrap_socket(
                httpd.socket, server_side=True
            )
            scheme = "https"
        console.print(f"[green]🚀 JARVIS P2P Server listening on port {port} ({scheme})...[/green]")
        httpd.serve_forever()

def run_udp_discovery_listener(http_port, discovery_port=11436):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('', discovery_port))
        while True:
            data, addr = sock.recvfrom(1024)
            if data == b"JARVIS_DISCOVERY_REQUEST":
                from core.config import load_config
                name = load_config().get("jarvis_name", "JARVIS-PEER")
                sock.sendto(f"JARVIS_DISCOVERY_RESPONSE|{name}|{http_port}".encode(), addr)
    except Exception as e: console.print(f"[dim]UDP Discovery Error: {e}[/dim]")
    finally: sock.close()

def scan_for_jarvis_peers(port=11435, timeout=1.5, use_tls=None, verify_tls=False):
    from core.config import load_config
    cfg = load_config()
    scheme = _p2p_scheme(use_tls, cfg)
    if scheme == "https" and not verify_tls:
        _quiet_insecure_warnings()
    found_peers = set()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); sock.settimeout(timeout)
    try:
        sock.sendto(b"JARVIS_DISCOVERY_REQUEST", ('<broadcast>', 11436))
        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                if data.startswith(b"JARVIS_DISCOVERY_RESPONSE"): found_peers.add(addr[0])
            except socket.timeout: break
    except: pass
    finally: sock.close()

    # Subnet Fallback
    from tools.network import get_local_ip
    local_ip = get_local_ip()
    prefix = ".".join(local_ip.split(".")[:-1]) + "."
    def check_peer(ip):
        try:
            r = requests.post(f"{scheme}://{ip}:{port}", json={"action": "status"},
                              timeout=0.3, verify=verify_tls)
            if r.status_code == 200: return ip
        except: pass
        return None
    with ThreadPoolExecutor(max_workers=50) as executor:
        for res in executor.map(check_peer, [prefix + str(i) for i in range(1, 255)]):
            if res: found_peers.add(res)

    # Global Registry Fallback
    try:
        from core.global_p2p import get_global_peers
        for peer in get_global_peers():
            ep = peer.get("endpoint")
            if ep: found_peers.add(ep)
    except: pass

    return list(found_peers)

def send_remote_command(peer_ip, action, params, port=11435, use_tls=None, verify_tls=False):
    """POST a command to a peer.

    TLS is opt-in (use_tls=True or "p2p_use_tls": true in config); the scheme
    then becomes https. verify_tls=False (default) skips certificate
    verification so self-signed LAN certs work — set it True for CA-signed
    certs you want validated.
    """
    from core.config import load_config
    cfg = load_config()
    scheme = _p2p_scheme(use_tls, cfg)
    if scheme == "https" and not verify_tls:
        _quiet_insecure_warnings()
    url = f"{scheme}://{peer_ip}:{port}"
    data = {"action": action, "version": CURRENT_VERSION, "token": cfg.get("p2p_token"), **params}
    stream = params.get("stream", False)
    try:
        r = requests.post(url, json=data, timeout=30, stream=stream, verify=verify_tls)
        if r.status_code == 200:
            return {"ok": True, "stream": r.iter_content(chunk_size=None)} if stream else {"ok": True, "data": r.text}
        return {"ok": False, "error": f"Error {r.status_code}: {r.text}"}
    except Exception as e: return {"ok": False, "error": str(e)}

def p2p_status_report(use_tls=None, verify_tls=False):
    from rich.table import Table
    from rich.live import Live
    from core.config import load_config
    cfg = load_config()
    scheme = _p2p_scheme(use_tls, cfg)
    if scheme == "https" and not verify_tls:
        _quiet_insecure_warnings()
    table = Table(title="JARVIS P2P Swarm Status", border_style="cyan")
    table.add_column("Peer IP"); table.add_column("Name"); table.add_column("Version"); table.add_column("Compatibility"); table.add_column("Model"); table.add_column("Latency")
    console.print("[bold cyan]📡 Discovering JARVIS instances...[/bold cyan]")
    with Live(table, refresh_per_second=4):
        peers = scan_for_jarvis_peers(use_tls=use_tls, verify_tls=verify_tls)
        for ip in peers:
            start = time.time()
            try:
                r = requests.post(f"{scheme}://{ip}:11435", json={"action": "status"}, timeout=0.8, verify=verify_tls)
                if r.status_code == 200:
                    data = r.json()
                    lat = f"{(time.time() - start)*1000:.1f}ms"
                    sync = "[green]✓ MATCH[/green]" if data.get("version") == CURRENT_VERSION else "[yellow]⚠ LEGACY[/yellow]"
                    table.add_row(ip, data.get("name"), data.get("version"), sync, data.get("model"), lat)
            except: pass

def p2p_token_menu():
    console.print("[yellow]⚠️ Tokens are transferred over plaintext HTTP. "
                  "Only request tokens from peers on networks you trust.[/yellow]")
    peers = scan_for_jarvis_peers()
    if not peers: console.print("[yellow]No peers found.[/yellow]"); return
    table = Table(title="Peer Tokens")
    table.add_column("ID"); table.add_column("IP"); table.add_column("Tokens")
    peer_map = {}
    for i, ip in enumerate(peers):
        res = send_remote_command(ip, "list_tokens", {})
        if res["ok"]:
            tokens = json.loads(res["data"])
            table.add_row(str(i+1), ip, ", ".join(tokens))
            peer_map[str(i+1)] = {"ip": ip, "tokens": tokens}
    console.print(table)
    choice = Prompt.ask("Select ID to request token", default="b")
    if choice in peer_map:
        p = peer_map[choice]
        t_choice = Prompt.ask("Select token", choices=p["tokens"])
        res = send_remote_command(p["ip"], "get_token", {"provider": t_choice})
        if res["ok"]:
            from core.services import set_api_key
            set_api_key(t_choice, res["data"])
            console.print("[green]✅ Token received![/green]")

def start_server_background(port=11435, use_tls=None, certfile=None, keyfile=None):
    t = threading.Thread(target=run_p2p_server,
                         kwargs={"port": port, "use_tls": use_tls,
                                 "certfile": certfile, "keyfile": keyfile},
                         daemon=True)
    t.start()
    return t
