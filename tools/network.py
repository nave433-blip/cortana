import socket
import subprocess
import os
import platform
from rich.console import Console
from rich.table import Table

console = Console()

def get_local_ip():
    """Get the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def ping_device(ip):
    """Ping a specific IP to see if it's alive."""
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', '-W', '1', ip]
    return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

def scan_network():
    """Perform a simple ping sweep of the local subnet (Fing-style)."""
    local_ip = get_local_ip()
    prefix = ".".join(local_ip.split(".")[:-1]) + "."
    
    console.print(f"[bold cyan]Scanning local network subnet: {prefix}0/24[/bold cyan]")
    
    table = Table(title="Network Discovery", border_style="cyan")
    table.add_column("IP Address", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Hostname", style="white")

    # Limit scan to first 50 IPs for speed in CLI
    for i in range(1, 51):
        ip = prefix + str(i)
        if ping_device(ip):
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except socket.error:
                hostname = "Unknown"
            table.add_row(ip, "ALIVE", hostname)
    
    return table

def scan_ports(ip, port_range=(1, 1024)):
    """Scan for open ports on a target IP."""
    console.print(f"[bold cyan]Scanning ports on {ip} ({port_range[0]}-{port_range[1]})...[/bold cyan]")
    
    open_ports = []
    for port in range(port_range[0], port_range[1] + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.1)
        if s.connect_ex((ip, port)) == 0:
            open_ports.append(port)
        s.close()
    
    return open_ports

from concurrent.futures import ThreadPoolExecutor

def scan_network_for_ollama():
    """Scan the local subnet for Ollama instances on port 11434."""
    subnet = "192.168.1"
    targets = [f"{subnet}.{i}" for i in range(1, 255)]
    found_hosts = []

    def check_host(ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex((ip, 11434)) == 0:
                    return f"http://{ip}:11434"
        except:
            pass
        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(check_host, targets)
        for res in results:
            if res:
                found_hosts.append(res)
    
    return found_hosts
