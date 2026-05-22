import psutil
import socket
from rich.console import Console
from rich.table import Table

console = Console()

def list_listening_ports():
    """List all processes listening on local ports."""
    table = Table(title="Local Listening Ports", border_style="magenta")
    table.add_column("Protocol", style="cyan")
    table.add_column("Local Address", style="white")
    table.add_column("Status", style="green")
    table.add_column("PID", style="yellow")
    table.add_column("Process Name", style="white")

    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'LISTEN':
            try:
                process = psutil.Process(conn.pid)
                name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                name = "Unknown"
            
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}"
            proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
            
            table.add_row(proto, laddr, conn.status, str(conn.pid), name)
    
    return table

def get_process_stats():
    """Return high-level system process and resource stats."""
    return {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "process_count": len(psutil.pids())
    }

def kill_process(pid):
    """Terminate a process by PID."""
    try:
        process = psutil.Process(pid)
        process.terminate()
        return f"Process {pid} ({process.name()}) terminated."
    except Exception as e:
        return f"Error killing process: {e}"
