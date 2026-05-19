import subprocess
import sys
from rich.console import Console
from rich.table import Table

console = Console()

def list_usb_devices():
    """List all USB devices currently connected to the computer."""
    if sys.platform == "darwin":
        # macOS specific
        try:
            cmd = "system_profiler SPUSBDataType"
            res = subprocess.getoutput(cmd)
            return res
        except Exception as e:
            return f"Error scanning USB: {e}"
    elif sys.platform == "linux":
        # Linux specific
        try:
            cmd = "lsusb"
            res = subprocess.getoutput(cmd)
            return res
        except Exception as e:
            return f"Error scanning USB: {e}"
    else:
        return "Unsupported platform for hardware probing."

def probe_ports():
    """General hardware port probe."""
    if sys.platform == "darwin":
        try:
            # Get a list of all hardware data types
            cmd = "system_profiler -listDataTypes"
            types = subprocess.getoutput(cmd)
            return types
        except Exception as e:
            return f"Error probing hardware: {e}"
    return "Unsupported platform for general probing."

def get_hardware_summary():
    table = Table(title="Hardware Port Summary", border_style="cyan")
    table.add_column("Type", style="cyan")
    table.add_column("Status", style="green")
    
    # Check USB
    usb = list_usb_devices()
    usb_count = usb.count("Product ID:") if "Product ID:" in usb else 0
    table.add_row("USB Devices", f"{usb_count} detected")
    
    # Other ports check could go here
    
    return table

def check_system_specs():
    """Detects basic hardware capabilities: returns dict with ram_gb, is_apple_silicon, has_gpu, is_low_end."""
    specs = {
        "ram_gb": 0,
        "is_apple_silicon": False,
        "has_gpu": False,
        "is_low_end": False
    }
    
    try:
        if sys.platform == "darwin":
            # macOS check for Apple Silicon and RAM
            cpu_info = subprocess.getoutput("sysctl -n machdep.cpu.brand_string").lower()
            ram_bytes = int(subprocess.getoutput("sysctl -n hw.memsize"))
            specs["ram_gb"] = ram_bytes // (1024 ** 3)
            
            if "apple" in cpu_info:
                specs["is_apple_silicon"] = True
                specs["has_gpu"] = True # Apple Silicon implies unified memory/GPU
            else:
                gpu_info = subprocess.getoutput("system_profiler SPDisplaysDataType").lower()
                if "amd" in gpu_info or "nvidia" in gpu_info:
                    specs["has_gpu"] = True
                
        elif sys.platform == "linux":
            # Linux check for RAM and GPU
            mem_info = subprocess.getoutput("awk '/MemTotal/ {print $2}' /proc/meminfo")
            if mem_info.isdigit():
                specs["ram_gb"] = int(mem_info) // (1024 * 1024)
            
            lspci_out = subprocess.getoutput("lspci | grep -i vga").lower()
            if "nvidia" in lspci_out or "amd" in lspci_out:
                specs["has_gpu"] = True
                
    except Exception as e:
        console.print(f"[dim]Warning: Failed to probe hardware specs: {e}[/dim]")
        
    # Define "low end" as less than 16GB RAM or lacking a dedicated/unified GPU
    if specs["ram_gb"] < 16 or not specs["has_gpu"]:
        specs["is_low_end"] = True
        
    return specs

